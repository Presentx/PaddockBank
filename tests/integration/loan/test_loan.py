from datetime import date

from tests.utils import DbUtils, ObjectGenerator, PayloadGenerator, RequestGenerator

UNKNOWN_KEY = "00000000-0000-0000-0000-000000000000"

# R$ 90.000,00 depositados HOJE numa conta nova: o saldo médio diário da
# janela de 90 dias é 9000000 / 90 = 100000 (R$ 1.000,00), e o limite de
# crédito é 50% disso: 50000 (R$ 500,00).
SPONSORSHIP = 9000000
LIMIT_AFTER_SPONSORSHIP = 50000

# A parcela da tabela Price para 30000 em 3 vezes a 3,5% ao mês:
#   30000 × 0,035 / (1 − 1,035^−3) = 10708,03 → 10708 centavos.
# O número está escrito à mão de propósito: o teste não importa a
# fórmula de src/, ele cobra o resultado.
PRICE_30000_IN_3_AT_350_BPS = 10708
PRICE_30000_IN_3_AT_250_BPS = 10504

FAR_FUTURE = {"reference_date": "2099-12-31"}


def get_account(team: dict) -> dict:
    status, account = RequestGenerator.GET_account(team["account_key"], team["member_key"])
    assert status == 200

    return account


def create_funded_team() -> dict:
    team = ObjectGenerator.create_team()
    ObjectGenerator.deposit(team, SPONSORSHIP)

    return team


def drain_account(team: dict) -> None:
    """Zera o saldo da conta pagando um fornecedor (na carência, sem tarifa)."""
    balance = get_account(team)["balance"]
    subsystem_key = ObjectGenerator.create_subsystem(team, budget=balance)
    supplier_key = ObjectGenerator.create_supplier(team)
    expense_key = ObjectGenerator.create_expense(team, subsystem_key, supplier_key, amount=balance)

    status, response = RequestGenerator.PUT_expense_approve(expense_key, team["member_key"])
    assert status == 200
    assert response["balance_after"] == 0


class TestLoan:
    def test_credit_limit_follows_the_average_daily_balance(self):
        """Dinheiro que chegou hoje pesa um dia em noventa."""
        team = ObjectGenerator.create_team()
        assert get_account(team)["available_credit_limit"] == 0

        ObjectGenerator.deposit(team, SPONSORSHIP)
        assert get_account(team)["available_credit_limit"] == LIMIT_AFTER_SPONSORSHIP

    def test_contracts_loan_and_generates_price_installments(self):
        team = create_funded_team()
        payload = PayloadGenerator.create_loan_payload(30000, installments=3)

        status, loan = RequestGenerator.POST_loan(team["account_key"], team["member_key"], payload)
        assert status == 201
        assert loan["status"] == "ACTIVE"
        assert loan["principal"] == 30000
        assert loan["monthly_rate_bps"] == 350
        assert loan["installments"] == 3
        assert loan["installment_amount"] == PRICE_30000_IN_3_AT_350_BPS
        assert loan["balance_after"] == SPONSORSHIP + 30000
        assert loan["requester_member_key"] == team["member_key"]

        numbers = []
        due_dates = []
        for installment in loan["installment_list"]:
            numbers.append(installment["number"])
            due_dates.append(installment["due_date"])
            assert installment["amount"] == PRICE_30000_IN_3_AT_350_BPS
            assert installment["status"] == "PENDING"
            assert installment["paid_at"] is None

        assert numbers == [1, 2, 3]
        assert due_dates == sorted(due_dates)
        # A primeira parcela vence um mês depois da contratação, nunca hoje.
        assert due_dates[0] > date.today().isoformat()

        status, statement = RequestGenerator.GET_statement(team["account_key"], team["member_key"])
        disbursement = statement["data"][0]
        assert disbursement["type"] == "LOAN_DISBURSEMENT"
        assert disbursement["amount"] == 30000
        assert disbursement["balance_after"] == SPONSORSHIP + 30000

        status, fetched = RequestGenerator.GET_loan(loan["loan_key"], team["member_key"])
        assert status == 200
        assert fetched["installment_list"] == loan["installment_list"]

        account = get_account(team)
        assert len(account["open_loans"]) == 1
        assert account["open_loans"][0]["loan_key"] == loan["loan_key"]

    def test_pro_plan_has_a_lower_rate(self):
        team = create_funded_team()

        status, _response = RequestGenerator.PATCH_account(team["account_key"], team["member_key"], {"plan": "PRO"})
        assert status == 200

        status, loan = RequestGenerator.POST_loan(
            team["account_key"], team["member_key"], PayloadGenerator.create_loan_payload(30000, installments=3)
        )
        assert status == 201
        assert loan["monthly_rate_bps"] == 250
        assert loan["installment_amount"] == PRICE_30000_IN_3_AT_250_BPS

    def test_repeated_contract_credits_only_once(self):
        """A mesma idempotency_key devolve o crédito original, com 200."""
        team = create_funded_team()
        payload = PayloadGenerator.create_loan_payload(30000)

        status, first = RequestGenerator.POST_loan(team["account_key"], team["member_key"], payload)
        assert status == 201

        status, second = RequestGenerator.POST_loan(team["account_key"], team["member_key"], payload)
        assert status == 200
        assert second == first

        assert get_account(team)["balance"] == SPONSORSHIP + 30000

    def test_refuses_amount_above_the_limit(self):
        team = create_funded_team()

        status, response = RequestGenerator.POST_loan(
            team["account_key"],
            team["member_key"],
            PayloadGenerator.create_loan_payload(LIMIT_AFTER_SPONSORSHIP + 1),
        )
        assert status == 409
        assert response["code"] == "PDK-CRD-002"
        assert get_account(team)["balance"] == SPONSORSHIP

        # Exatamente o limite cabe.
        status, _response = RequestGenerator.POST_loan(
            team["account_key"], team["member_key"], PayloadGenerator.create_loan_payload(LIMIT_AFTER_SPONSORSHIP)
        )
        assert status == 201

    def test_outstanding_debt_consumes_the_limit(self):
        """O saldo devedor (as parcelas em aberto) desconta do limite."""
        team = create_funded_team()

        status, _response = RequestGenerator.POST_loan(
            team["account_key"], team["member_key"], PayloadGenerator.create_loan_payload(30000, installments=3)
        )
        assert status == 201

        # Saldo médio: (9000000 + 30000) / 90 = 100333; metade: 50166;
        # menos as três parcelas de 10708 em aberto: 18042.
        remaining_limit = 50166 - 3 * PRICE_30000_IN_3_AT_350_BPS
        assert get_account(team)["available_credit_limit"] == remaining_limit

        status, response = RequestGenerator.POST_loan(
            team["account_key"], team["member_key"], PayloadGenerator.create_loan_payload(remaining_limit + 1)
        )
        assert status == 409
        assert response["code"] == "PDK-CRD-002"

    def test_only_finance_contracts(self):
        team = create_funded_team()
        common_member_key = ObjectGenerator.create_member(team)

        status, response = RequestGenerator.POST_loan(
            team["account_key"], common_member_key, PayloadGenerator.create_loan_payload(10000)
        )
        assert status == 403
        assert response["code"] == "PDK-GEN-004"

    def test_schema_refuses_invalid_loan(self):
        team = create_funded_team()

        for installments in [0, 13, 2.5]:
            payload = PayloadGenerator.create_loan_payload(10000)
            payload["installments"] = installments

            status, response = RequestGenerator.POST_loan(team["account_key"], team["member_key"], payload)
            assert status == 400, f"installments {installments!r} foi aceito"
            assert response["code"] == "PDK-GEN-001"

    def test_loan_of_another_team_looks_like_it_does_not_exist(self):
        team = create_funded_team()
        intruder = ObjectGenerator.create_team()

        status, loan = RequestGenerator.POST_loan(
            team["account_key"], team["member_key"], PayloadGenerator.create_loan_payload(10000)
        )
        assert status == 201

        status, response = RequestGenerator.GET_loan(loan["loan_key"], intruder["member_key"])
        assert status == 404
        assert response["code"] == "PDK-CRD-001"

        status, response = RequestGenerator.GET_loan(UNKNOWN_KEY, intruder["member_key"])
        assert status == 404
        assert response["code"] == "PDK-CRD-001"

        status, response = RequestGenerator.POST_loan(
            team["account_key"], intruder["member_key"], PayloadGenerator.create_loan_payload(10000)
        )
        assert status == 404
        assert response["code"] == "PDK-ACCT-001"


class TestLoanInstallmentCharge:
    """A cobrança diária: POST /loan-installments/charge-due.

    Os testes daqui começam por DbUtils.rollback(), e não é enfeite: a
    cobrança varre as parcelas vencidas do banco INTEIRO, e a resposta
    conta quantas cobrou. Com o que os outros testes deixaram pra trás,
    essa contagem não seria deste teste.
    """

    def test_charges_due_installments_only_once(self):
        DbUtils.rollback()
        team = create_funded_team()

        status, loan = RequestGenerator.POST_loan(
            team["account_key"], team["member_key"], PayloadGenerator.create_loan_payload(30000, installments=3)
        )
        assert status == 201
        balance = SPONSORSHIP + 30000

        # Sem corpo, a referência é hoje — e nada venceu ainda.
        status, response = RequestGenerator.POST_charge_due()
        assert status == 200
        assert response == {"charged": 0, "late": 0}

        status, response = RequestGenerator.POST_charge_due(FAR_FUTURE)
        assert status == 200
        assert response == {"charged": 3, "late": 0}

        balance = balance - 3 * PRICE_30000_IN_3_AT_350_BPS
        assert get_account(team)["balance"] == balance

        status, fetched = RequestGenerator.GET_loan(loan["loan_key"], team["member_key"])
        assert fetched["status"] == "PAID"
        for installment in fetched["installment_list"]:
            assert installment["status"] == "PAID"
            assert installment["paid_at"] is not None

        # Repetir a cobrança não cobra de novo: parcela PAID é ignorada.
        status, response = RequestGenerator.POST_charge_due(FAR_FUTURE)
        assert status == 200
        assert response == {"charged": 0, "late": 0}
        assert get_account(team)["balance"] == balance

        status, statement = RequestGenerator.GET_statement(team["account_key"], team["member_key"])
        installment_lines = []
        for line in statement["data"]:
            if line["type"] == "LOAN_INSTALLMENT":
                installment_lines.append(line["amount"])
        assert installment_lines == [-PRICE_30000_IN_3_AT_350_BPS] * 3

        # Crédito quitado sai da lista de créditos em aberto.
        assert get_account(team)["open_loans"] == []

    def test_installment_without_balance_goes_late_and_blocks_new_loans(self):
        DbUtils.rollback()
        team = create_funded_team()

        status, loan = RequestGenerator.POST_loan(
            team["account_key"], team["member_key"], PayloadGenerator.create_loan_payload(30000, installments=2)
        )
        assert status == 201
        installment_amount = loan["installment_amount"]

        drain_account(team)

        status, response = RequestGenerator.POST_charge_due(FAR_FUTURE)
        assert status == 200
        assert response == {"charged": 0, "late": 2}

        # A parcela não é paga pela metade nem deixa a conta negativa.
        assert get_account(team)["balance"] == 0

        status, fetched = RequestGenerator.GET_loan(loan["loan_key"], team["member_key"])
        assert fetched["status"] == "LATE"

        status, response = RequestGenerator.POST_loan(
            team["account_key"], team["member_key"], PayloadGenerator.create_loan_payload(1000)
        )
        assert status == 409
        assert response["code"] == "PDK-CRD-003"

        # Entra dinheiro pra UMA parcela: a cobrança do dia seguinte paga
        # essa, e a outra continua em atraso.
        ObjectGenerator.deposit(team, installment_amount)

        status, response = RequestGenerator.POST_charge_due(FAR_FUTURE)
        assert response == {"charged": 1, "late": 1}

        status, fetched = RequestGenerator.GET_loan(loan["loan_key"], team["member_key"])
        assert fetched["status"] == "LATE"
        assert fetched["installment_list"][0]["status"] == "PAID"
        assert fetched["installment_list"][1]["status"] == "LATE"

        ObjectGenerator.deposit(team, installment_amount)

        status, response = RequestGenerator.POST_charge_due(FAR_FUTURE)
        assert response == {"charged": 1, "late": 0}

        status, fetched = RequestGenerator.GET_loan(loan["loan_key"], team["member_key"])
        assert fetched["status"] == "PAID"
        assert get_account(team)["balance"] == 0

    def test_schema_refuses_invalid_reference_date(self):
        status, response = RequestGenerator.POST_charge_due({"reference_date": "31/12/2099"})
        assert status == 400
        assert response["code"] == "PDK-GEN-001"

        # Formato certo, data que não existe no calendário: 400, nunca 500.
        status, response = RequestGenerator.POST_charge_due({"reference_date": "2099-02-30"})
        assert status == 400
        assert response["code"] == "PDK-GEN-001"

        status, response = RequestGenerator.POST_charge_due({"data": "2099-12-31"})
        assert status == 400
        assert response["code"] == "PDK-GEN-001"
