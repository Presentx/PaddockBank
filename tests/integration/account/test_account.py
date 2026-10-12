from concurrent.futures import ThreadPoolExecutor

from tests.utils import ObjectGenerator, PayloadGenerator, RequestGenerator

UNKNOWN_KEY = "00000000-0000-0000-0000-000000000000"


class TestAccount:
    def test_deposit_credits_the_account(self):
        team = ObjectGenerator.create_team()
        payload = PayloadGenerator.create_deposit_payload(500000)

        status, response = RequestGenerator.POST_deposit(team["pix_key"], payload)
        assert status == 201
        assert response["balance_after"] == 500000
        transaction_key = response["transaction_key"]

        status, account = RequestGenerator.GET_account(team["account_key"], team["member_key"])
        assert status == 200
        assert account["balance"] == 500000

        status, statement = RequestGenerator.GET_statement(team["account_key"], team["member_key"])
        assert status == 200
        assert len(statement["data"]) == 1

        line = statement["data"][0]
        assert line["transaction_key"] == transaction_key
        assert line["type"] == "DEPOSIT"
        assert line["amount"] == 500000
        assert line["balance_after"] == 500000
        assert line["counterparty_name"] == payload["payer_name"]
        assert line["counterparty_document"] == payload["payer_document"]
        assert line["subsystem_key"] is None

    def test_repeated_deposit_credits_only_once(self):
        """A mesma idempotency_key devolve a transação original, com 200, sem creditar de novo."""
        team = ObjectGenerator.create_team()
        payload = PayloadGenerator.create_deposit_payload(120000)

        status, first = RequestGenerator.POST_deposit(team["pix_key"], payload)
        assert status == 201

        status, second = RequestGenerator.POST_deposit(team["pix_key"], payload)
        assert status == 200
        assert second == first

        status, account = RequestGenerator.GET_account(team["account_key"], team["member_key"])
        assert account["balance"] == 120000

    def test_simultaneous_copies_of_a_deposit_credit_only_once(self):
        """Oito cópias do mesmo aviso de pagamento ao mesmo tempo: um crédito só.

        É o caso que a conferência simples ("já vi esta chave?") não
        pega: todas as cópias perguntam antes de qualquer uma gravar.
        Quem as põe em fila é a trava da conta.
        """
        team = ObjectGenerator.create_team()
        payload = PayloadGenerator.create_deposit_payload(70000)

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = []
            for _copy in range(8):
                futures.append(executor.submit(RequestGenerator.POST_deposit, team["pix_key"], payload))

            results = []
            for future in futures:
                results.append(future.result())

        statuses = []
        transaction_keys = set()
        for status, response in results:
            statuses.append(status)
            transaction_keys.add(response["transaction_key"])

        assert sorted(statuses) == [200] * 7 + [201]
        assert len(transaction_keys) == 1

        status, account = RequestGenerator.GET_account(team["account_key"], team["member_key"])
        assert account["balance"] == 70000

    def test_deposit_to_unknown_pix_key(self):
        status, response = RequestGenerator.POST_deposit(UNKNOWN_KEY, PayloadGenerator.create_deposit_payload(1000))
        assert status == 404
        assert response["code"] == "PDK-ACCT-003"

    def test_schema_refuses_invalid_deposit(self):
        team = ObjectGenerator.create_team()

        for invalid_amount in [0, -100, 10.5, "1000"]:
            payload = PayloadGenerator.create_deposit_payload(1000)
            payload["amount"] = invalid_amount

            status, response = RequestGenerator.POST_deposit(team["pix_key"], payload)
            assert status == 400, f"amount {invalid_amount!r} foi aceito"
            assert response["code"] == "PDK-GEN-001"

        payload = PayloadGenerator.create_deposit_payload(1000)
        del payload["idempotency_key"]

        status, response = RequestGenerator.POST_deposit(team["pix_key"], payload)
        assert status == 400
        assert response["code"] == "PDK-GEN-001"

    def test_statement_is_newest_first_and_adds_up_to_the_balance(self):
        """Cada linha traz o saldo resultante, e a soma das linhas é o saldo da conta."""
        team = ObjectGenerator.create_team()

        for amount in [100000, 25000, 4000]:
            ObjectGenerator.deposit(team, amount)

        status, statement = RequestGenerator.GET_statement(team["account_key"], team["member_key"])
        assert status == 200

        amounts = []
        balances = []
        for line in statement["data"]:
            amounts.append(line["amount"])
            balances.append(line["balance_after"])

        assert amounts == [4000, 25000, 100000]
        assert balances == [129000, 125000, 100000]

        status, account = RequestGenerator.GET_account(team["account_key"], team["member_key"])
        assert account["balance"] == sum(amounts)

        status, page = RequestGenerator.GET_statement(team["account_key"], team["member_key"], {"limit": 2})
        assert len(page["data"]) == 2
        assert page["is_last_page"] is False

        status, page = RequestGenerator.GET_statement(team["account_key"], team["member_key"], {"limit": 2, "page": 1})
        assert len(page["data"]) == 1
        assert page["is_last_page"] is True

    def test_statement_line_carries_the_request_id(self):
        """O X-Request-ID da requisição fica gravado na linha do extrato que ela gerou."""
        team = ObjectGenerator.create_team()

        status, _response = RequestGenerator.send(
            "POST",
            f"/pix/{team['pix_key']}/deposit",
            payload=PayloadGenerator.create_deposit_payload(1000),
            headers={"X-Request-ID": "deposito-rastreavel-42"},
        )
        assert status == 201

        status, statement = RequestGenerator.GET_statement(team["account_key"], team["member_key"])
        assert statement["data"][0]["request_id"] == "deposito-rastreavel-42"

    def test_changes_plan(self):
        team = ObjectGenerator.create_team()

        status, response = RequestGenerator.PATCH_account(team["account_key"], team["member_key"], {"plan": "PRO"})
        assert status == 200
        assert response == {"account_key": team["account_key"], "plan": "PRO"}

        status, account = RequestGenerator.GET_account(team["account_key"], team["member_key"])
        assert account["plan"] == "PRO"
        assert account["outgoing_fee_bps"] == 50

        status, response = RequestGenerator.PATCH_account(team["account_key"], team["member_key"], {"plan": "GOLD"})
        assert status == 400
        assert response["code"] == "PDK-GEN-001"

    def test_only_finance_changes_plan(self):
        team = ObjectGenerator.create_team()
        common_member_key = ObjectGenerator.create_member(team)

        status, response = RequestGenerator.PATCH_account(team["account_key"], common_member_key, {"plan": "PRO"})
        assert status == 403
        assert response["code"] == "PDK-GEN-004"

    def test_account_of_another_team_looks_like_it_does_not_exist(self):
        team = ObjectGenerator.create_team()
        intruder = ObjectGenerator.create_team()

        status, response = RequestGenerator.GET_account(team["account_key"], intruder["member_key"])
        assert status == 404
        assert response["code"] == "PDK-ACCT-001"

        status, response = RequestGenerator.GET_statement(team["account_key"], intruder["member_key"])
        assert status == 404
        assert response["code"] == "PDK-ACCT-001"

        status, response = RequestGenerator.PATCH_account(team["account_key"], intruder["member_key"], {"plan": "PRO"})
        assert status == 404
        assert response["code"] == "PDK-ACCT-001"

    def test_statement_filter_by_unknown_subsystem(self):
        team = ObjectGenerator.create_team()
        other_team = ObjectGenerator.create_team()
        foreign_subsystem_key = ObjectGenerator.create_subsystem(other_team)

        for subsystem_key in [UNKNOWN_KEY, foreign_subsystem_key]:
            status, response = RequestGenerator.GET_statement(
                team["account_key"], team["member_key"], {"subsystem_key": subsystem_key}
            )
            assert status == 404
            assert response["code"] == "PDK-SUBS-001"
