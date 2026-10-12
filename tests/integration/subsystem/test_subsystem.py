from tests.utils import ObjectGenerator, PayloadGenerator, RequestGenerator

UNKNOWN_KEY = "00000000-0000-0000-0000-000000000000"


class TestSubsystem:
    def test_creates_subsystem(self):
        team = ObjectGenerator.create_team()
        owner_role_key = ObjectGenerator.create_role(team, name="Powertrain")
        payload = PayloadGenerator.create_subsystem_payload(owner_role_key, budget=250000, name="Motor")

        status, response = RequestGenerator.POST_subsystem(team["team_key"], team["member_key"], payload)
        assert status == 201
        subsystem_key = response["subsystem_key"]

        status, response = RequestGenerator.GET_subsystems(team["team_key"], team["member_key"])
        assert status == 200
        assert response["data"] == [
            {
                "subsystem_key": subsystem_key,
                "name": "Motor",
                "owner_role_key": owner_role_key,
                "owner_role_name": "Powertrain",
                "budget": 250000,
                "committed": 0,
                "available": 250000,
            }
        ]

    def test_refuses_duplicated_name_in_the_team(self):
        team = ObjectGenerator.create_team()
        payload = PayloadGenerator.create_subsystem_payload(team["finance_role_key"])

        status, _response = RequestGenerator.POST_subsystem(team["team_key"], team["member_key"], payload)
        assert status == 201

        status, response = RequestGenerator.POST_subsystem(team["team_key"], team["member_key"], payload)
        assert status == 409
        assert response["code"] == "PDK-SUBS-002"

    def test_schema_refuses_money_that_is_not_integer_cents(self):
        """Dinheiro é centavo inteiro: fração, texto e negativo morrem no schema."""
        team = ObjectGenerator.create_team()

        for invalid_budget in [1500.5, "1500", -1]:
            payload = PayloadGenerator.create_subsystem_payload(team["finance_role_key"], budget=invalid_budget)

            status, response = RequestGenerator.POST_subsystem(team["team_key"], team["member_key"], payload)
            assert status == 400, f"budget {invalid_budget!r} foi aceito"
            assert response["code"] == "PDK-GEN-001"

    def test_owner_role_missing_or_from_another_team(self):
        team = ObjectGenerator.create_team()
        other_team = ObjectGenerator.create_team()

        status, response = RequestGenerator.POST_subsystem(
            team["team_key"], team["member_key"], PayloadGenerator.create_subsystem_payload(UNKNOWN_KEY)
        )
        assert status == 404
        assert response["code"] == "PDK-ROLE-001"

        status, response = RequestGenerator.POST_subsystem(
            team["team_key"],
            team["member_key"],
            PayloadGenerator.create_subsystem_payload(other_team["finance_role_key"]),
        )
        assert status == 422
        assert response["code"] == "PDK-GEN-003"

    def test_only_finance_manages_subsystems(self):
        team = ObjectGenerator.create_team()
        subsystem_key = ObjectGenerator.create_subsystem(team)
        common_member_key = ObjectGenerator.create_member(team)

        status, response = RequestGenerator.POST_subsystem(
            team["team_key"], common_member_key, PayloadGenerator.create_subsystem_payload(team["finance_role_key"])
        )
        assert status == 403
        assert response["code"] == "PDK-GEN-004"

        status, response = RequestGenerator.PATCH_subsystem(subsystem_key, common_member_key, {"budget": 1})
        assert status == 403
        assert response["code"] == "PDK-GEN-004"

    def test_updates_budget_and_shows_what_is_left(self):
        team = ObjectGenerator.create_team()
        subsystem_key = ObjectGenerator.create_subsystem(team, budget=100000)
        supplier_key = ObjectGenerator.create_supplier(team)
        ObjectGenerator.create_expense(team, subsystem_key, supplier_key, amount=30000)

        status, response = RequestGenerator.PATCH_subsystem(subsystem_key, team["member_key"], {"budget": 50000})
        assert status == 200
        assert response["budget"] == 50000
        assert response["committed"] == 30000
        assert response["available"] == 20000

    def test_refuses_budget_below_what_is_committed(self):
        """O teto não desce abaixo do que os pedidos já reservaram."""
        team = ObjectGenerator.create_team()
        subsystem_key = ObjectGenerator.create_subsystem(team, budget=100000)
        supplier_key = ObjectGenerator.create_supplier(team)
        ObjectGenerator.create_expense(team, subsystem_key, supplier_key, amount=30000)

        status, response = RequestGenerator.PATCH_subsystem(subsystem_key, team["member_key"], {"budget": 29999})
        assert status == 409
        assert response["code"] == "PDK-SUBS-003"

        status, response = RequestGenerator.PATCH_subsystem(subsystem_key, team["member_key"], {"budget": 30000})
        assert status == 200
        assert response["available"] == 0

    def test_subsystem_of_another_team_looks_like_it_does_not_exist(self):
        team = ObjectGenerator.create_team()
        intruder = ObjectGenerator.create_team()
        subsystem_key = ObjectGenerator.create_subsystem(team)

        status, response = RequestGenerator.PATCH_subsystem(subsystem_key, intruder["member_key"], {"budget": 1})
        assert status == 404
        assert response["code"] == "PDK-SUBS-001"
