from tests.utils import ObjectGenerator, PayloadGenerator, RequestGenerator

UNKNOWN_KEY = "00000000-0000-0000-0000-000000000000"


def find_role(roles_page: dict, role_key: str) -> dict:
    for role in roles_page["data"]:
        if role["role_key"] == role_key:
            return role

    return None


class TestRole:
    def test_creates_role_under_a_parent(self):
        team = ObjectGenerator.create_team()

        payload = PayloadGenerator.create_role_payload(name="Capitania", parent_role_key=team["finance_role_key"])
        status, response = RequestGenerator.POST_role(team["team_key"], team["member_key"], payload)
        assert status == 201
        role_key = response["role_key"]

        status, roles_page = RequestGenerator.GET_roles(team["team_key"], team["member_key"])
        assert status == 200
        assert len(roles_page["data"]) == 2
        assert roles_page["is_last_page"] is True

        assert find_role(roles_page, team["finance_role_key"]) == {
            "role_key": team["finance_role_key"],
            "name": "Diretoria Financeira",
            "parent_role_key": None,
            "is_finance": True,
        }
        assert find_role(roles_page, role_key) == {
            "role_key": role_key,
            "name": "Capitania",
            "parent_role_key": team["finance_role_key"],
            "is_finance": False,
        }

    def test_refuses_duplicated_name_in_the_team(self):
        team = ObjectGenerator.create_team()
        ObjectGenerator.create_role(team, name="Powertrain")

        status, response = RequestGenerator.POST_role(
            team["team_key"], team["member_key"], PayloadGenerator.create_role_payload(name="Powertrain")
        )
        assert status == 409
        assert response["code"] == "PDK-ROLE-002"

    def test_same_name_in_another_team_is_fine(self):
        """O nome do cargo é único POR EQUIPE, não no banco inteiro."""
        team = ObjectGenerator.create_team()
        other_team = ObjectGenerator.create_team()

        ObjectGenerator.create_role(team, name="Aerodinâmica")
        ObjectGenerator.create_role(other_team, name="Aerodinâmica")

    def test_only_finance_creates_roles(self):
        team = ObjectGenerator.create_team()
        common_member_key = ObjectGenerator.create_member(team)

        status, response = RequestGenerator.POST_role(
            team["team_key"], common_member_key, PayloadGenerator.create_role_payload()
        )
        assert status == 403
        assert response["code"] == "PDK-GEN-004"

    def test_parent_from_body_missing_or_from_another_team(self):
        """Chave do CORPO: inexistente é 404; de outra equipe é 422."""
        team = ObjectGenerator.create_team()
        other_team = ObjectGenerator.create_team()

        status, response = RequestGenerator.POST_role(
            team["team_key"], team["member_key"], PayloadGenerator.create_role_payload(parent_role_key=UNKNOWN_KEY)
        )
        assert status == 404
        assert response["code"] == "PDK-ROLE-001"

        status, response = RequestGenerator.POST_role(
            team["team_key"],
            team["member_key"],
            PayloadGenerator.create_role_payload(parent_role_key=other_team["finance_role_key"]),
        )
        assert status == 422
        assert response["code"] == "PDK-GEN-003"

    def test_renames_and_moves_a_role(self):
        team = ObjectGenerator.create_team()
        captain_key = ObjectGenerator.create_role(team, name="Capitania")
        brakes_key = ObjectGenerator.create_role(team, name="Freios")

        status, response = RequestGenerator.PATCH_role(
            brakes_key, team["member_key"], {"name": "Freios e Suspensão", "parent_role_key": captain_key}
        )
        assert status == 200
        assert response == {
            "role_key": brakes_key,
            "name": "Freios e Suspensão",
            "parent_role_key": captain_key,
            "is_finance": False,
        }

        status, response = RequestGenerator.PATCH_role(brakes_key, team["member_key"], {"parent_role_key": None})
        assert status == 200
        assert response["parent_role_key"] is None

    def test_finance_role_can_be_renamed(self):
        team = ObjectGenerator.create_team()

        status, response = RequestGenerator.PATCH_role(
            team["finance_role_key"], team["member_key"], {"name": "Tesouraria"}
        )
        assert status == 200
        assert response["name"] == "Tesouraria"
        assert response["is_finance"] is True

    def test_refuses_parent_that_would_close_a_cycle(self):
        """O cargo superior não pode ser o próprio cargo, nem um subordinado dele."""
        team = ObjectGenerator.create_team()
        top_key = ObjectGenerator.create_role(team)
        middle_key = ObjectGenerator.create_role(team, parent_role_key=top_key)
        bottom_key = ObjectGenerator.create_role(team, parent_role_key=middle_key)

        for invalid_parent_key in [top_key, middle_key, bottom_key]:
            status, response = RequestGenerator.PATCH_role(
                top_key, team["member_key"], {"parent_role_key": invalid_parent_key}
            )
            assert status == 409, f"aceitou {invalid_parent_key} como superior"
            assert response["code"] == "PDK-ROLE-003"

    def test_role_of_another_team_looks_like_it_does_not_exist(self):
        team = ObjectGenerator.create_team()
        intruder = ObjectGenerator.create_team()

        status, response = RequestGenerator.PATCH_role(
            team["finance_role_key"], intruder["member_key"], {"name": "Invadido"}
        )
        assert status == 404
        assert response["code"] == "PDK-ROLE-001"

        status, response = RequestGenerator.GET_roles(team["team_key"], intruder["member_key"])
        assert status == 404
        assert response["code"] == "PDK-TEAM-001"

    def test_schema_refuses_empty_patch(self):
        team = ObjectGenerator.create_team()

        status, response = RequestGenerator.PATCH_role(team["finance_role_key"], team["member_key"], {})
        assert status == 400
        assert response["code"] == "PDK-GEN-001"

    def test_list_is_paginated(self):
        team = ObjectGenerator.create_team()
        ObjectGenerator.create_role(team)
        ObjectGenerator.create_role(team)

        status, response = RequestGenerator.GET_roles(team["team_key"], team["member_key"], {"limit": 2})
        assert status == 200
        assert len(response["data"]) == 2
        assert response["is_last_page"] is False

        status, response = RequestGenerator.GET_roles(team["team_key"], team["member_key"], {"limit": 2, "page": 1})
        assert status == 200
        assert len(response["data"]) == 1
        assert response["is_last_page"] is True

        status, response = RequestGenerator.GET_roles(team["team_key"], team["member_key"], {"limit": 500})
        assert status == 400
        assert response["code"] == "PDK-GEN-001"
