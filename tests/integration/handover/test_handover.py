from concurrent.futures import ThreadPoolExecutor

from tests.utils import DbUtils, ObjectGenerator, PayloadGenerator, RequestGenerator

UNKNOWN_KEY = "00000000-0000-0000-0000-000000000000"

# A tarifa de passagem de gestão do plano FREE: R$ 49,90.
HANDOVER_FEE = 4990


def get_account(team: dict, member_key: str) -> dict:
    status, account = RequestGenerator.GET_account(team["account_key"], member_key)
    assert status == 200

    return account


def create_successor(team: dict) -> tuple:
    """Um responsável comum pra assumir, e o cargo pra onde vai quem sai."""
    successor_key = ObjectGenerator.create_member(team)
    outgoing_role_key = ObjectGenerator.create_role(team, name="Conselho")

    return successor_key, outgoing_role_key


class TestHandover:
    """A passagem de gestão: POST /team/{team_key}/handover."""

    def test_handover_swaps_the_finance_role_and_keeps_the_account(self):
        """Na carência a passagem é isenta; o cargo e a titularidade trocam de mãos."""
        team = ObjectGenerator.create_team()
        successor_key, outgoing_role_key = create_successor(team)
        ObjectGenerator.deposit(team, 100000)

        subsystem_key = ObjectGenerator.create_subsystem(team)
        supplier_key = ObjectGenerator.create_supplier(team)
        pending_expense_key = ObjectGenerator.create_expense(team, subsystem_key, supplier_key, amount=15000)

        payload = PayloadGenerator.create_handover_payload(successor_key, outgoing_role_key)
        status, response = RequestGenerator.POST_handover(team["team_key"], team["member_key"], payload)
        assert status == 200
        assert response["finance_member_key"] == successor_key
        assert response["fee"] == 0
        assert response["balance_after"] == 100000

        # O sucessor é o titular; quem saiu foi pro cargo que indicou.
        status, fetched_team = RequestGenerator.GET_team(team["team_key"], successor_key)
        assert fetched_team["finance_member"]["member_key"] == successor_key
        assert fetched_team["finance_member"]["role_key"] == team["finance_role_key"]

        status, former = RequestGenerator.GET_member(team["member_key"], successor_key)
        assert former["role_key"] == outgoing_role_key
        assert former["is_finance"] is False
        assert former["status"] == "ACTIVE"

        # A conta e a chave PIX são as mesmas.
        account = get_account(team, successor_key)
        assert account["pix_key"] == team["pix_key"]
        assert account["holder"]["member_key"] == successor_key
        assert account["balance"] == 100000

        # Quem saiu não aprova mais; quem entrou aprova o pedido que já estava pendente.
        status, response = RequestGenerator.PUT_expense_approve(pending_expense_key, team["member_key"])
        assert status == 403
        assert response["code"] == "PDK-GEN-004"

        status, response = RequestGenerator.PUT_expense_approve(pending_expense_key, successor_key)
        assert status == 200
        assert response["status"] == "PAID"

    def test_fee_is_charged_even_without_balance(self):
        """Plano FREE, depois da carência, conta zerada: a tarifa deixa o saldo negativo."""
        team = ObjectGenerator.create_team()
        successor_key, outgoing_role_key = create_successor(team)
        DbUtils.expire_grace(team["account_key"])

        payload = PayloadGenerator.create_handover_payload(successor_key, outgoing_role_key)
        status, response = RequestGenerator.send(
            "POST",
            f"/team/{team['team_key']}/handover",
            team["member_key"],
            payload,
            headers={"X-Request-ID": "passagem-rastreavel-3"},
        )
        assert status == 200
        assert response["fee"] == HANDOVER_FEE
        assert response["balance_after"] == -HANDOVER_FEE

        assert get_account(team, successor_key)["balance"] == -HANDOVER_FEE

        status, statement = RequestGenerator.GET_statement(team["account_key"], successor_key)
        assert len(statement["data"]) == 1
        fee_line = statement["data"][0]
        assert fee_line["type"] == "HANDOVER_FEE"
        assert fee_line["amount"] == -HANDOVER_FEE
        assert fee_line["balance_after"] == -HANDOVER_FEE
        assert fee_line["request_id"] == "passagem-rastreavel-3"

    def test_negative_account_pays_nothing_until_deposits_cover_it(self):
        """O negativo é só da tarifa de passagem: pagamento nenhum o aproveita."""
        team = ObjectGenerator.create_team()
        successor_key, outgoing_role_key = create_successor(team)
        subsystem_key = ObjectGenerator.create_subsystem(team)
        supplier_key = ObjectGenerator.create_supplier(team)
        expense_key = ObjectGenerator.create_expense(team, subsystem_key, supplier_key, amount=1000)
        DbUtils.expire_grace(team["account_key"])

        status, _response = RequestGenerator.POST_handover(
            team["team_key"],
            team["member_key"],
            PayloadGenerator.create_handover_payload(successor_key, outgoing_role_key),
        )
        assert status == 200

        status, response = RequestGenerator.PUT_expense_approve(expense_key, successor_key)
        assert status == 409
        assert response["code"] == "PDK-ACCT-002"

        # As entradas seguintes compensam a tarifa.
        deposit = ObjectGenerator.deposit(team, 6000)
        assert deposit["balance_after"] == 6000 - HANDOVER_FEE

        # 1010 de saldo: cobre o pedido de 1000 e os 10 da tarifa mínima.
        status, response = RequestGenerator.PUT_expense_approve(expense_key, successor_key)
        assert status == 200
        assert response["fee"] == 10
        assert response["balance_after"] == 0

        # De volta ao positivo, a conta não guarda permissão de negativo:
        # um pedido acima do saldo é recusado.
        another_expense_key = ObjectGenerator.create_expense(
            team, subsystem_key, supplier_key, member_key=successor_key, amount=1
        )
        status, response = RequestGenerator.PUT_expense_approve(another_expense_key, successor_key)
        assert status == 409
        assert response["code"] == "PDK-ACCT-002"

    def test_repeated_handover_does_not_charge_or_swap_again(self):
        """A repetição devolve o resultado original — mesmo vinda de quem já não é o financeiro."""
        team = ObjectGenerator.create_team()
        successor_key, outgoing_role_key = create_successor(team)
        DbUtils.expire_grace(team["account_key"])

        payload = PayloadGenerator.create_handover_payload(successor_key, outgoing_role_key)

        status, first = RequestGenerator.POST_handover(team["team_key"], team["member_key"], payload)
        assert status == 200

        status, second = RequestGenerator.POST_handover(team["team_key"], team["member_key"], payload)
        assert status == 200
        assert second == first

        assert get_account(team, successor_key)["balance"] == -HANDOVER_FEE

        status, fetched_team = RequestGenerator.GET_team(team["team_key"], successor_key)
        assert fetched_team["finance_member"]["member_key"] == successor_key

        # Com OUTRA chave, é um pedido novo — e quem saiu já não pode fazê-lo.
        status, response = RequestGenerator.POST_handover(
            team["team_key"],
            team["member_key"],
            PayloadGenerator.create_handover_payload(successor_key, outgoing_role_key),
        )
        assert status == 403
        assert response["code"] == "PDK-GEN-004"

    def test_simultaneous_copies_of_a_handover_take_effect_once(self):
        """Oito cópias da mesma passagem ao mesmo tempo: uma tarifa, uma troca."""
        team = ObjectGenerator.create_team()
        successor_key, outgoing_role_key = create_successor(team)
        DbUtils.expire_grace(team["account_key"])

        payload = PayloadGenerator.create_handover_payload(successor_key, outgoing_role_key)

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = []
            for _copy in range(8):
                futures.append(
                    executor.submit(RequestGenerator.POST_handover, team["team_key"], team["member_key"], payload)
                )

            results = []
            for future in futures:
                results.append(future.result())

        for status, response in results:
            assert status == 200
            assert response == results[0][1]

        assert get_account(team, successor_key)["balance"] == -HANDOVER_FEE

        status, statement = RequestGenerator.GET_statement(team["account_key"], successor_key)
        assert len(statement["data"]) == 1

    def test_pro_plan_is_exempt(self):
        team = ObjectGenerator.create_team()
        successor_key, outgoing_role_key = create_successor(team)
        DbUtils.expire_grace(team["account_key"])

        status, _response = RequestGenerator.PATCH_account(team["account_key"], team["member_key"], {"plan": "PRO"})
        assert status == 200

        status, response = RequestGenerator.POST_handover(
            team["team_key"],
            team["member_key"],
            PayloadGenerator.create_handover_payload(successor_key, outgoing_role_key),
        )
        assert status == 200
        assert response["fee"] == 0
        assert response["balance_after"] == 0

        status, statement = RequestGenerator.GET_statement(team["account_key"], successor_key)
        assert statement["data"] == []

    def test_refuses_invalid_successor_or_outgoing_role(self):
        team = ObjectGenerator.create_team()
        other_team = ObjectGenerator.create_team()
        successor_key, outgoing_role_key = create_successor(team)

        inactive_key = ObjectGenerator.create_member(team)
        status, _response = RequestGenerator.PATCH_member(inactive_key, team["member_key"], {"active": False})
        assert status == 200

        cases = [
            (UNKNOWN_KEY, outgoing_role_key, 404, "PDK-MEMB-001"),
            (other_team["member_key"], outgoing_role_key, 422, "PDK-GEN-003"),
            (inactive_key, outgoing_role_key, 422, "PDK-MEMB-005"),
            (team["member_key"], outgoing_role_key, 409, "PDK-MEMB-007"),
            (successor_key, UNKNOWN_KEY, 404, "PDK-ROLE-001"),
            (successor_key, other_team["finance_role_key"], 422, "PDK-GEN-003"),
            (successor_key, team["finance_role_key"], 409, "PDK-ROLE-004"),
        ]

        for incoming_member_key, role_key, expected_status, expected_code in cases:
            payload = PayloadGenerator.create_handover_payload(incoming_member_key, role_key)

            status, response = RequestGenerator.POST_handover(team["team_key"], team["member_key"], payload)
            assert status == expected_status, f"esperava {expected_code}, veio {response}"
            assert response["code"] == expected_code

        # Nenhuma das recusas trocou o titular.
        status, fetched_team = RequestGenerator.GET_team(team["team_key"], team["member_key"])
        assert fetched_team["finance_member"]["member_key"] == team["member_key"]

    def test_only_finance_hands_over(self):
        team = ObjectGenerator.create_team()
        successor_key, outgoing_role_key = create_successor(team)
        payload = PayloadGenerator.create_handover_payload(successor_key, outgoing_role_key)

        # Ninguém se promove a financeiro.
        status, response = RequestGenerator.POST_handover(team["team_key"], successor_key, payload)
        assert status == 403
        assert response["code"] == "PDK-GEN-004"

        status, response = RequestGenerator.POST_handover(team["team_key"], None, payload)
        assert status == 401
        assert response["code"] == "PDK-GEN-006"

    def test_team_of_another_member_looks_like_it_does_not_exist(self):
        team = ObjectGenerator.create_team()
        intruder = ObjectGenerator.create_team()
        successor_key, outgoing_role_key = create_successor(team)

        status, response = RequestGenerator.POST_handover(
            team["team_key"],
            intruder["member_key"],
            PayloadGenerator.create_handover_payload(successor_key, outgoing_role_key),
        )
        assert status == 404
        assert response["code"] == "PDK-TEAM-001"

    def test_schema_requires_the_idempotency_key(self):
        team = ObjectGenerator.create_team()
        successor_key, outgoing_role_key = create_successor(team)

        payload = PayloadGenerator.create_handover_payload(successor_key, outgoing_role_key)
        del payload["idempotency_key"]

        status, response = RequestGenerator.POST_handover(team["team_key"], team["member_key"], payload)
        assert status == 400
        assert response["code"] == "PDK-GEN-001"
