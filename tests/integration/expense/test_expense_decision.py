from concurrent.futures import ThreadPoolExecutor

from tests.utils import DbUtils, ObjectGenerator, PayloadGenerator, RequestGenerator

UNKNOWN_KEY = "00000000-0000-0000-0000-000000000000"


def get_balance(team: dict) -> int:
    status, account = RequestGenerator.GET_account(team["account_key"], team["member_key"])
    assert status == 200

    return account["balance"]


def get_committed(team: dict, subsystem_key: str) -> int:
    status, response = RequestGenerator.GET_subsystems(team["team_key"], team["member_key"], {"limit": 100})
    assert status == 200

    for subsystem in response["data"]:
        if subsystem["subsystem_key"] == subsystem_key:
            return subsystem["committed"]

    return None


def extract_trail(expense: dict) -> list:
    trail = []
    for status_event in expense["status_events"]:
        trail.append(status_event["status"])

    return trail


class TestExpenseDecision:
    """Aprovar, recusar e cancelar: o segundo controle de saldo — o da conta."""

    def test_approve_pays_the_supplier_without_fee_during_grace(self):
        """Nos primeiros 60 dias não há tarifa: sai só o valor do pedido."""
        team = ObjectGenerator.create_team()
        requester_key = ObjectGenerator.create_member(team)
        subsystem_key = ObjectGenerator.create_subsystem(team)
        supplier_key = ObjectGenerator.create_supplier(team)
        ObjectGenerator.deposit(team, 100000)

        expense_key = ObjectGenerator.create_expense(team, subsystem_key, supplier_key, requester_key, amount=15000)

        status, response = RequestGenerator.PUT_expense_approve(
            expense_key, team["member_key"], headers={"X-Request-ID": "aprovacao-rastreavel-9"}
        )
        assert status == 200
        assert response == {"expense_key": expense_key, "status": "PAID", "fee": 0, "balance_after": 85000}

        status, expense = RequestGenerator.GET_expense(expense_key, requester_key)
        assert expense["status"] == "PAID"
        assert expense["approver"]["member_key"] == team["member_key"]
        assert extract_trail(expense) == ["PENDING", "PAID"]
        assert expense["status_events"][1]["member_key"] == team["member_key"]
        assert expense["status_events"][1]["request_id"] == "aprovacao-rastreavel-9"

        status, statement = RequestGenerator.GET_statement(team["account_key"], team["member_key"])
        payment = statement["data"][0]
        assert payment["type"] == "SUPPLIER_PAYMENT"
        assert payment["amount"] == -15000
        assert payment["balance_after"] == 85000
        assert payment["subsystem_key"] == subsystem_key
        assert payment["request_id"] == "aprovacao-rastreavel-9"
        assert len(statement["data"]) == 2

        # O que estava reservado agora está gasto, e continua contando no teto.
        assert get_committed(team, subsystem_key) == 15000

    def test_approve_charges_the_outgoing_fee_after_grace(self):
        """Plano FREE: 1,0% do valor, como uma linha FEE própria no extrato."""
        team = ObjectGenerator.create_team()
        subsystem_key = ObjectGenerator.create_subsystem(team)
        supplier_key = ObjectGenerator.create_supplier(team)
        ObjectGenerator.deposit(team, 100000)
        DbUtils.expire_grace(team["account_key"])

        expense_key = ObjectGenerator.create_expense(team, subsystem_key, supplier_key, amount=15000)

        status, response = RequestGenerator.PUT_expense_approve(expense_key, team["member_key"])
        assert status == 200
        assert response["fee"] == 150
        assert response["balance_after"] == 84850

        status, statement = RequestGenerator.GET_statement(team["account_key"], team["member_key"])
        fee_line = statement["data"][0]
        payment_line = statement["data"][1]

        assert fee_line["type"] == "FEE"
        assert fee_line["amount"] == -150
        assert fee_line["balance_after"] == 84850
        assert payment_line["type"] == "SUPPLIER_PAYMENT"
        assert payment_line["amount"] == -15000
        assert payment_line["balance_after"] == 85000

        # Extrato consistente: a soma das linhas é o saldo.
        total = 0
        for line in statement["data"]:
            total = total + line["amount"]
        assert total == get_balance(team) == 84850

    def test_outgoing_fee_has_a_minimum(self):
        """1% de R$ 5,00 seria R$ 0,05: vale o mínimo de R$ 0,10."""
        team = ObjectGenerator.create_team()
        subsystem_key = ObjectGenerator.create_subsystem(team)
        supplier_key = ObjectGenerator.create_supplier(team)
        ObjectGenerator.deposit(team, 10000)
        DbUtils.expire_grace(team["account_key"])

        expense_key = ObjectGenerator.create_expense(team, subsystem_key, supplier_key, amount=500)

        status, response = RequestGenerator.PUT_expense_approve(expense_key, team["member_key"])
        assert status == 200
        assert response["fee"] == 10
        assert response["balance_after"] == 9490

    def test_pro_plan_pays_half_the_fee(self):
        team = ObjectGenerator.create_team()
        subsystem_key = ObjectGenerator.create_subsystem(team)
        supplier_key = ObjectGenerator.create_supplier(team)
        ObjectGenerator.deposit(team, 100000)
        DbUtils.expire_grace(team["account_key"])

        status, _response = RequestGenerator.PATCH_account(team["account_key"], team["member_key"], {"plan": "PRO"})
        assert status == 200

        expense_key = ObjectGenerator.create_expense(team, subsystem_key, supplier_key, amount=15000)

        status, response = RequestGenerator.PUT_expense_approve(expense_key, team["member_key"])
        assert status == 200
        assert response["fee"] == 75
        assert response["balance_after"] == 84925

    def test_reimbursement_pays_the_requester(self):
        """No reembolso, quem recebe é o responsável que pagou do próprio bolso."""
        team = ObjectGenerator.create_team()
        subsystem_key = ObjectGenerator.create_subsystem(team)
        supplier_key = ObjectGenerator.create_supplier(team)
        ObjectGenerator.deposit(team, 50000)

        role_key = ObjectGenerator.create_role(team)
        requester_payload = PayloadGenerator.create_member_payload(role_key, name="Emerson Pilar")
        status, response = RequestGenerator.POST_member(team["team_key"], team["member_key"], requester_payload)
        assert status == 201
        requester_key = response["member_key"]

        expense_key = ObjectGenerator.create_expense(
            team, subsystem_key, supplier_key, requester_key, kind="REIMBURSEMENT", invoice_number="NF-55", amount=8000
        )

        status, _response = RequestGenerator.PUT_expense_approve(expense_key, team["member_key"])
        assert status == 200

        status, statement = RequestGenerator.GET_statement(team["account_key"], team["member_key"])
        line = statement["data"][0]
        assert line["type"] == "REIMBURSEMENT"
        assert line["amount"] == -8000
        assert line["counterparty_name"] == "Emerson Pilar"
        assert line["counterparty_document"] == requester_payload["document_number"]

    def test_insufficient_balance_keeps_the_expense_pending(self):
        """Sem saldo pro valor MAIS a tarifa: 409, nada gravado, reserva mantida."""
        team = ObjectGenerator.create_team()
        subsystem_key = ObjectGenerator.create_subsystem(team)
        supplier_key = ObjectGenerator.create_supplier(team)
        ObjectGenerator.deposit(team, 15000)
        DbUtils.expire_grace(team["account_key"])

        # O saldo cobre os 15000 do pedido, mas não os 150 da tarifa.
        expense_key = ObjectGenerator.create_expense(team, subsystem_key, supplier_key, amount=15000)

        status, response = RequestGenerator.PUT_expense_approve(expense_key, team["member_key"])
        assert status == 409
        assert response["code"] == "PDK-ACCT-002"

        assert get_balance(team) == 15000
        assert get_committed(team, subsystem_key) == 15000

        status, expense = RequestGenerator.GET_expense(expense_key, team["member_key"])
        assert expense["status"] == "PENDING"
        assert extract_trail(expense) == ["PENDING"]

        # O dinheiro entra, e o MESMO pedido pode ser aprovado.
        ObjectGenerator.deposit(team, 150)

        status, response = RequestGenerator.PUT_expense_approve(expense_key, team["member_key"])
        assert status == 200
        assert response["balance_after"] == 0

    def test_expense_is_paid_only_once(self):
        team = ObjectGenerator.create_team()
        subsystem_key = ObjectGenerator.create_subsystem(team)
        supplier_key = ObjectGenerator.create_supplier(team)
        ObjectGenerator.deposit(team, 100000)

        expense_key = ObjectGenerator.create_expense(team, subsystem_key, supplier_key, amount=15000)

        status, _response = RequestGenerator.PUT_expense_approve(expense_key, team["member_key"])
        assert status == 200

        status, response = RequestGenerator.PUT_expense_approve(expense_key, team["member_key"])
        assert status == 409
        assert response["code"] == "PDK-EXP-002"

        assert get_balance(team) == 85000

    def test_simultaneous_approvals_pay_only_once(self):
        """Oito aprovações do mesmo pedido ao mesmo tempo: um pagamento só.

        Todas entram em fila na trava do pedido; a primeira paga, e as
        outras sete já leem PAID.
        """
        team = ObjectGenerator.create_team()
        subsystem_key = ObjectGenerator.create_subsystem(team)
        supplier_key = ObjectGenerator.create_supplier(team)
        ObjectGenerator.deposit(team, 100000)

        expense_key = ObjectGenerator.create_expense(team, subsystem_key, supplier_key, amount=15000)

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = []
            for _request in range(8):
                futures.append(executor.submit(RequestGenerator.PUT_expense_approve, expense_key, team["member_key"]))

            statuses = []
            for future in futures:
                statuses.append(future.result()[0])

        assert sorted(statuses) == [200] + [409] * 7
        assert get_balance(team) == 85000

        status, statement = RequestGenerator.GET_statement(team["account_key"], team["member_key"])
        assert len(statement["data"]) == 2

    def test_simultaneous_approvals_never_overdraw_the_account(self):
        """Seis pedidos de 30000 aprovados ao mesmo tempo, com saldo pra três.

        Pedidos DIFERENTES não disputam a trava do pedido — disputam a
        da conta. Sem ela, todos leriam 100000 e todos pagariam.
        """
        team = ObjectGenerator.create_team()
        subsystem_key = ObjectGenerator.create_subsystem(team, budget=1000000)
        supplier_key = ObjectGenerator.create_supplier(team)
        ObjectGenerator.deposit(team, 100000)

        expense_keys = []
        for _expense in range(6):
            expense_keys.append(ObjectGenerator.create_expense(team, subsystem_key, supplier_key, amount=30000))

        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = []
            for expense_key in expense_keys:
                futures.append(executor.submit(RequestGenerator.PUT_expense_approve, expense_key, team["member_key"]))

            results = []
            for future in futures:
                results.append(future.result())

        statuses = []
        for status, response in results:
            statuses.append(status)
            if status == 409:
                assert response["code"] == "PDK-ACCT-002"

        assert sorted(statuses) == [200] * 3 + [409] * 3
        assert get_balance(team) == 10000

    def test_only_finance_approves_and_rejects(self):
        team = ObjectGenerator.create_team()
        requester_key = ObjectGenerator.create_member(team)
        subsystem_key = ObjectGenerator.create_subsystem(team)
        supplier_key = ObjectGenerator.create_supplier(team)
        ObjectGenerator.deposit(team, 100000)

        expense_key = ObjectGenerator.create_expense(team, subsystem_key, supplier_key, requester_key)

        # Nem quem pediu aprova o próprio pedido.
        status, response = RequestGenerator.PUT_expense_approve(expense_key, requester_key)
        assert status == 403
        assert response["code"] == "PDK-GEN-004"

        status, response = RequestGenerator.PUT_expense_reject(expense_key, requester_key)
        assert status == 403
        assert response["code"] == "PDK-GEN-004"

        status, response = RequestGenerator.PUT_expense_approve(expense_key, None)
        assert status == 401
        assert response["code"] == "PDK-GEN-006"

        assert get_balance(team) == 100000

    def test_reject_releases_the_budget_and_records_the_reason(self):
        team = ObjectGenerator.create_team()
        subsystem_key = ObjectGenerator.create_subsystem(team)
        supplier_key = ObjectGenerator.create_supplier(team)

        expense_key = ObjectGenerator.create_expense(team, subsystem_key, supplier_key, amount=15000)
        assert get_committed(team, subsystem_key) == 15000

        status, response = RequestGenerator.PUT_expense_reject(expense_key, team["member_key"], "Sem três orçamentos")
        assert status == 200
        assert response == {"expense_key": expense_key, "status": "REJECTED"}

        assert get_committed(team, subsystem_key) == 0

        status, expense = RequestGenerator.GET_expense(expense_key, team["member_key"])
        assert expense["status"] == "REJECTED"
        assert expense["reason"] == "Sem três orçamentos"
        assert extract_trail(expense) == ["PENDING", "REJECTED"]

        # REJECTED é final.
        status, response = RequestGenerator.PUT_expense_approve(expense_key, team["member_key"])
        assert status == 409
        assert response["code"] == "PDK-EXP-002"

    def test_reject_requires_a_reason(self):
        team = ObjectGenerator.create_team()
        subsystem_key = ObjectGenerator.create_subsystem(team)
        supplier_key = ObjectGenerator.create_supplier(team)
        expense_key = ObjectGenerator.create_expense(team, subsystem_key, supplier_key)

        status, response = RequestGenerator.send(
            "PUT", f"/expense/{expense_key}/reject", team["member_key"], payload={}
        )
        assert status == 400
        assert response["code"] == "PDK-GEN-001"

    def test_only_the_requester_cancels(self):
        """Nem o financeiro cancela o pedido de outro: pra isso existe a recusa."""
        team = ObjectGenerator.create_team()
        requester_key = ObjectGenerator.create_member(team)
        subsystem_key = ObjectGenerator.create_subsystem(team)
        supplier_key = ObjectGenerator.create_supplier(team)

        expense_key = ObjectGenerator.create_expense(team, subsystem_key, supplier_key, requester_key, amount=15000)

        status, response = RequestGenerator.PUT_expense_cancel(expense_key, team["member_key"])
        assert status == 403
        assert response["code"] == "PDK-EXP-004"
        assert get_committed(team, subsystem_key) == 15000

        status, response = RequestGenerator.PUT_expense_cancel(expense_key, requester_key)
        assert status == 200
        assert response == {"expense_key": expense_key, "status": "CANCELED"}
        assert get_committed(team, subsystem_key) == 0

        status, response = RequestGenerator.PUT_expense_cancel(expense_key, requester_key)
        assert status == 409
        assert response["code"] == "PDK-EXP-002"

    def test_approval_and_rejection_at_the_same_time_decide_only_once(self):
        """Aprovar e recusar o mesmo pedido juntos: uma decisão vale, a outra leva 409.

        E o dinheiro e o orçamento ficam coerentes com a que valeu.
        """
        team = ObjectGenerator.create_team()
        subsystem_key = ObjectGenerator.create_subsystem(team)
        supplier_key = ObjectGenerator.create_supplier(team)
        ObjectGenerator.deposit(team, 100000)

        expense_key = ObjectGenerator.create_expense(team, subsystem_key, supplier_key, amount=15000)

        with ThreadPoolExecutor(max_workers=2) as executor:
            approval = executor.submit(RequestGenerator.PUT_expense_approve, expense_key, team["member_key"])
            rejection = executor.submit(RequestGenerator.PUT_expense_reject, expense_key, team["member_key"])

            statuses = [approval.result()[0], rejection.result()[0]]

        assert sorted(statuses) == [200, 409]

        status, expense = RequestGenerator.GET_expense(expense_key, team["member_key"])

        if expense["status"] == "PAID":
            assert get_balance(team) == 85000
            assert get_committed(team, subsystem_key) == 15000
        else:
            assert expense["status"] == "REJECTED"
            assert get_balance(team) == 100000
            assert get_committed(team, subsystem_key) == 0

    def test_invoice_follows_the_expense_status(self):
        """Nota em pedido pago não volta; em pedido recusado, fica livre de novo."""
        team = ObjectGenerator.create_team()
        subsystem_key = ObjectGenerator.create_subsystem(team)
        supplier_key = ObjectGenerator.create_supplier(team)
        ObjectGenerator.deposit(team, 100000)

        paid_key = ObjectGenerator.create_expense(
            team, subsystem_key, supplier_key, kind="REIMBURSEMENT", invoice_number="NF-PAGA"
        )
        status, _response = RequestGenerator.PUT_expense_approve(paid_key, team["member_key"])
        assert status == 200

        payload = PayloadGenerator.create_expense_payload(
            subsystem_key, supplier_key, kind="REIMBURSEMENT", invoice_number="NF-PAGA"
        )
        status, response = RequestGenerator.POST_expense(team["member_key"], payload)
        assert status == 409
        assert response["code"] == "PDK-EXP-003"

        rejected_key = ObjectGenerator.create_expense(
            team, subsystem_key, supplier_key, kind="REIMBURSEMENT", invoice_number="NF-RECUSADA"
        )
        status, _response = RequestGenerator.PUT_expense_reject(rejected_key, team["member_key"])
        assert status == 200

        payload = PayloadGenerator.create_expense_payload(
            subsystem_key, supplier_key, kind="REIMBURSEMENT", invoice_number="NF-RECUSADA"
        )
        status, _response = RequestGenerator.POST_expense(team["member_key"], payload)
        assert status == 201

    def test_expense_of_another_team_looks_like_it_does_not_exist(self):
        """IDOR: nem ler, nem aprovar, nem recusar, nem cancelar o pedido dos outros."""
        team = ObjectGenerator.create_team()
        intruder = ObjectGenerator.create_team()
        subsystem_key = ObjectGenerator.create_subsystem(team)
        supplier_key = ObjectGenerator.create_supplier(team)
        ObjectGenerator.deposit(team, 100000)

        expense_key = ObjectGenerator.create_expense(team, subsystem_key, supplier_key, amount=15000)

        attempts = [
            RequestGenerator.GET_expense(expense_key, intruder["member_key"]),
            RequestGenerator.PUT_expense_approve(expense_key, intruder["member_key"]),
            RequestGenerator.PUT_expense_reject(expense_key, intruder["member_key"]),
            RequestGenerator.PUT_expense_cancel(expense_key, intruder["member_key"]),
            RequestGenerator.GET_expense(UNKNOWN_KEY, intruder["member_key"]),
        ]

        for status, response in attempts:
            assert status == 404
            assert response["code"] == "PDK-EXP-001"

        status, response = RequestGenerator.GET_expenses(team["team_key"], intruder["member_key"])
        assert status == 404
        assert response["code"] == "PDK-TEAM-001"

        status, expense = RequestGenerator.GET_expense(expense_key, team["member_key"])
        assert expense["status"] == "PENDING"
        assert get_balance(team) == 100000
