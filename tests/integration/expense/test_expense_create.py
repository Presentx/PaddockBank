from concurrent.futures import ThreadPoolExecutor

from tests.utils import ObjectGenerator, PayloadGenerator, RequestGenerator

UNKNOWN_KEY = "00000000-0000-0000-0000-000000000000"


def get_subsystem(team: dict, subsystem_key: str) -> dict:
    status, response = RequestGenerator.GET_subsystems(team["team_key"], team["member_key"], {"limit": 100})
    assert status == 200

    for subsystem in response["data"]:
        if subsystem["subsystem_key"] == subsystem_key:
            return subsystem

    return None


class TestExpenseCreate:
    """O POST /expense: o primeiro controle de saldo — o teto do subsistema."""

    def test_creates_pending_expense_and_reserves_the_budget(self):
        team = ObjectGenerator.create_team()
        requester_key = ObjectGenerator.create_member(team)
        subsystem_key = ObjectGenerator.create_subsystem(team, budget=100000)
        supplier_key = ObjectGenerator.create_supplier(team)

        payload = PayloadGenerator.create_expense_payload(subsystem_key, supplier_key, amount=15000)
        status, response = RequestGenerator.POST_expense(
            requester_key, payload, headers={"X-Request-ID": "pedido-rastreavel-7"}
        )
        assert status == 201
        expense_key = response["expense_key"]
        assert response == {"expense_key": expense_key, "status": "PENDING"}

        subsystem = get_subsystem(team, subsystem_key)
        assert subsystem["committed"] == 15000
        assert subsystem["available"] == 85000

        status, expense = RequestGenerator.GET_expense(expense_key, requester_key)
        assert status == 200
        assert expense["status"] == "PENDING"
        assert expense["kind"] == "SUPPLIER_PAYMENT"
        assert expense["amount"] == 15000
        assert expense["subsystem_key"] == subsystem_key
        assert expense["supplier_key"] == supplier_key
        assert expense["requester"]["member_key"] == requester_key
        assert expense["approver"] is None

        # A trilha começa no próprio registro, com quem pediu e com o
        # X-Request-ID da requisição que o criou.
        assert len(expense["status_events"]) == 1
        first_event = expense["status_events"][0]
        assert first_event["status"] == "PENDING"
        assert first_event["member_key"] == requester_key
        assert first_event["request_id"] == "pedido-rastreavel-7"
        assert first_event["event_datetime"] is not None

        # Solicitar não mexe na conta: o dinheiro só sai na aprovação.
        status, statement = RequestGenerator.GET_statement(team["account_key"], team["member_key"])
        assert statement["data"] == []

    def test_repeated_request_reserves_only_once(self):
        """A mesma idempotency_key do mesmo solicitante devolve o pedido original, com 200."""
        team = ObjectGenerator.create_team()
        subsystem_key = ObjectGenerator.create_subsystem(team, budget=100000)
        supplier_key = ObjectGenerator.create_supplier(team)
        payload = PayloadGenerator.create_expense_payload(subsystem_key, supplier_key, amount=40000)

        status, first = RequestGenerator.POST_expense(team["member_key"], payload)
        assert status == 201

        status, second = RequestGenerator.POST_expense(team["member_key"], payload)
        assert status == 200
        assert second == first

        assert get_subsystem(team, subsystem_key)["committed"] == 40000

    def test_same_idempotency_key_from_another_member_is_another_expense(self):
        """A chave é única POR SOLICITANTE: dois responsáveis podem coincidir."""
        team = ObjectGenerator.create_team()
        other_member_key = ObjectGenerator.create_member(team)
        subsystem_key = ObjectGenerator.create_subsystem(team)
        supplier_key = ObjectGenerator.create_supplier(team)
        payload = PayloadGenerator.create_expense_payload(subsystem_key, supplier_key, amount=1000)

        status, first = RequestGenerator.POST_expense(team["member_key"], payload)
        assert status == 201

        status, second = RequestGenerator.POST_expense(other_member_key, payload)
        assert status == 201
        assert second["expense_key"] != first["expense_key"]

    def test_refuses_expense_above_the_available_budget(self):
        team = ObjectGenerator.create_team()
        subsystem_key = ObjectGenerator.create_subsystem(team, budget=100000)
        supplier_key = ObjectGenerator.create_supplier(team)
        ObjectGenerator.create_expense(team, subsystem_key, supplier_key, amount=80000)

        payload = PayloadGenerator.create_expense_payload(subsystem_key, supplier_key, amount=20001)
        status, response = RequestGenerator.POST_expense(team["member_key"], payload)
        assert status == 409
        assert response["code"] == "PDK-SUBS-004"
        assert get_subsystem(team, subsystem_key)["committed"] == 80000

        # Exatamente o que resta cabe: o teto é "menor ou igual".
        payload = PayloadGenerator.create_expense_payload(subsystem_key, supplier_key, amount=20000)
        status, _response = RequestGenerator.POST_expense(team["member_key"], payload)
        assert status == 201
        assert get_subsystem(team, subsystem_key)["available"] == 0

    def test_simultaneous_expenses_never_exceed_the_budget(self):
        """O cenário da Figura 4 da RFC, com dez pedidos em vez de dois.

        Teto de 100000 com 80000 comprometidos; dez pedidos de 15000
        chegam ao mesmo tempo. Só UM cabe (80000 + 15000 = 95000; o
        segundo levaria a 110000). Sem a trava do subsistema, vários
        leriam 80000 e todos gravariam.
        """
        team = ObjectGenerator.create_team()
        subsystem_key = ObjectGenerator.create_subsystem(team, budget=100000)
        supplier_key = ObjectGenerator.create_supplier(team)
        ObjectGenerator.create_expense(team, subsystem_key, supplier_key, amount=80000)

        payloads = []
        for _request in range(10):
            payloads.append(PayloadGenerator.create_expense_payload(subsystem_key, supplier_key, amount=15000))

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for payload in payloads:
                futures.append(executor.submit(RequestGenerator.POST_expense, team["member_key"], payload))

            results = []
            for future in futures:
                results.append(future.result())

        statuses = []
        for status, response in results:
            statuses.append(status)
            if status == 409:
                assert response["code"] == "PDK-SUBS-004"

        assert sorted(statuses) == [201] + [409] * 9

        subsystem = get_subsystem(team, subsystem_key)
        assert subsystem["committed"] == 95000
        assert subsystem["committed"] <= subsystem["budget"]

    def test_reimbursement_requires_the_invoice_number(self):
        team = ObjectGenerator.create_team()
        subsystem_key = ObjectGenerator.create_subsystem(team)
        supplier_key = ObjectGenerator.create_supplier(team)

        payload = PayloadGenerator.create_expense_payload(subsystem_key, supplier_key, kind="REIMBURSEMENT")
        status, response = RequestGenerator.POST_expense(team["member_key"], payload)
        assert status == 400
        assert response["code"] == "PDK-GEN-001"

        payload = PayloadGenerator.create_expense_payload(
            subsystem_key, supplier_key, kind="REIMBURSEMENT", invoice_number="NF-2026-0001"
        )
        status, _response = RequestGenerator.POST_expense(team["member_key"], payload)
        assert status == 201

    def test_invoice_cannot_be_in_two_open_expenses(self):
        """A mesma nota do mesmo fornecedor não entra em dois pedidos pendentes."""
        team = ObjectGenerator.create_team()
        subsystem_key = ObjectGenerator.create_subsystem(team)
        supplier_key = ObjectGenerator.create_supplier(team)
        other_supplier_key = ObjectGenerator.create_supplier(team)

        ObjectGenerator.create_expense(
            team, subsystem_key, supplier_key, kind="REIMBURSEMENT", invoice_number="NF-100"
        )

        payload = PayloadGenerator.create_expense_payload(
            subsystem_key, supplier_key, kind="REIMBURSEMENT", invoice_number="NF-100"
        )
        status, response = RequestGenerator.POST_expense(team["member_key"], payload)
        assert status == 409
        assert response["code"] == "PDK-EXP-005"

        # O número é do FORNECEDOR: a NF-100 de outro fornecedor é outra nota.
        payload = PayloadGenerator.create_expense_payload(
            subsystem_key, other_supplier_key, kind="REIMBURSEMENT", invoice_number="NF-100"
        )
        status, _response = RequestGenerator.POST_expense(team["member_key"], payload)
        assert status == 201

    def test_simultaneous_expenses_with_the_same_invoice(self):
        """Seis pedidos com a mesma nota, em subsistemas diferentes, ao mesmo tempo: um só passa.

        Em subsistemas diferentes, a trava do subsistema NÃO os põe em
        fila. Quem segura a regra aqui é o índice único parcial do
        banco.
        """
        team = ObjectGenerator.create_team()
        supplier_key = ObjectGenerator.create_supplier(team)

        payloads = []
        for _request in range(6):
            subsystem_key = ObjectGenerator.create_subsystem(team)
            payloads.append(
                PayloadGenerator.create_expense_payload(
                    subsystem_key, supplier_key, kind="REIMBURSEMENT", invoice_number="NF-777"
                )
            )

        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = []
            for payload in payloads:
                futures.append(executor.submit(RequestGenerator.POST_expense, team["member_key"], payload))

            results = []
            for future in futures:
                results.append(future.result())

        statuses = []
        for status, response in results:
            statuses.append(status)
            if status == 409:
                assert response["code"] == "PDK-EXP-005"

        assert sorted(statuses) == [201] + [409] * 5

    def test_references_from_body_missing_or_from_another_team(self):
        """Chave do CORPO: inexistente é 404 do recurso; de outra equipe é 422."""
        team = ObjectGenerator.create_team()
        other_team = ObjectGenerator.create_team()
        subsystem_key = ObjectGenerator.create_subsystem(team)
        supplier_key = ObjectGenerator.create_supplier(team)
        foreign_subsystem_key = ObjectGenerator.create_subsystem(other_team)
        foreign_supplier_key = ObjectGenerator.create_supplier(other_team)

        cases = [
            (UNKNOWN_KEY, supplier_key, 404, "PDK-SUBS-001"),
            (subsystem_key, UNKNOWN_KEY, 404, "PDK-SUPP-001"),
            (foreign_subsystem_key, supplier_key, 422, "PDK-GEN-003"),
            (subsystem_key, foreign_supplier_key, 422, "PDK-GEN-003"),
        ]

        for case_subsystem_key, case_supplier_key, expected_status, expected_code in cases:
            payload = PayloadGenerator.create_expense_payload(case_subsystem_key, case_supplier_key)

            status, response = RequestGenerator.POST_expense(team["member_key"], payload)
            assert status == expected_status
            assert response["code"] == expected_code

        # Nenhuma das recusas reservou nada no subsistema da outra equipe.
        assert get_subsystem(other_team, foreign_subsystem_key)["committed"] == 0

    def test_requires_identity(self):
        team = ObjectGenerator.create_team()
        subsystem_key = ObjectGenerator.create_subsystem(team)
        supplier_key = ObjectGenerator.create_supplier(team)
        payload = PayloadGenerator.create_expense_payload(subsystem_key, supplier_key)

        status, response = RequestGenerator.POST_expense(None, payload)
        assert status == 401
        assert response["code"] == "PDK-GEN-006"

    def test_schema_refuses_requester_in_the_body(self):
        """Quem solicita sai da sessão: o corpo não aceita um campo com esse papel."""
        team = ObjectGenerator.create_team()
        subsystem_key = ObjectGenerator.create_subsystem(team)
        supplier_key = ObjectGenerator.create_supplier(team)

        payload = PayloadGenerator.create_expense_payload(subsystem_key, supplier_key)
        payload["requester_member_key"] = team["member_key"]

        status, response = RequestGenerator.POST_expense(team["member_key"], payload)
        assert status == 400
        assert response["code"] == "PDK-GEN-001"

    def test_lists_and_filters_by_status(self):
        team = ObjectGenerator.create_team()
        subsystem_key = ObjectGenerator.create_subsystem(team)
        supplier_key = ObjectGenerator.create_supplier(team)

        pending_key = ObjectGenerator.create_expense(team, subsystem_key, supplier_key, amount=1000)
        rejected_key = ObjectGenerator.create_expense(team, subsystem_key, supplier_key, amount=2000)

        status, _response = RequestGenerator.PUT_expense_reject(rejected_key, team["member_key"])
        assert status == 200

        status, response = RequestGenerator.GET_expenses(team["team_key"], team["member_key"])
        assert status == 200
        assert len(response["data"]) == 2
        assert "status_events" not in response["data"][0]

        status, response = RequestGenerator.GET_expenses(team["team_key"], team["member_key"], {"status": "PENDING"})
        assert len(response["data"]) == 1
        assert response["data"][0]["expense_key"] == pending_key

        status, response = RequestGenerator.GET_expenses(
            team["team_key"], team["member_key"], {"status": ["PENDING", "REJECTED"]}
        )
        assert len(response["data"]) == 2

        status, response = RequestGenerator.GET_expenses(team["team_key"], team["member_key"], {"status": "ABERTO"})
        assert status == 400
        assert response["code"] == "PDK-GEN-001"
