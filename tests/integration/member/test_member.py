from tests.utils import ObjectGenerator, PayloadGenerator, RequestGenerator

UNKNOWN_KEY = "00000000-0000-0000-0000-000000000000"


class TestMember:
    def test_creates_member(self):
        team = ObjectGenerator.create_team()
        role_key = ObjectGenerator.create_role(team, name="Powertrain")
        payload = PayloadGenerator.create_member_payload(role_key, name="Rubens Gonçalves")

        status, response = RequestGenerator.POST_member(team["team_key"], team["member_key"], payload)
        assert status == 201
        member_key = response["member_key"]

        status, response = RequestGenerator.GET_member(member_key, team["member_key"])
        assert status == 200
        assert response == {
            "member_key": member_key,
            "name": "Rubens Gonçalves",
            "document_number": payload["document_number"],
            "email": payload["email"],
            "phone": payload["phone"],
            "pix_key": payload["pix_key"],
            "role_key": role_key,
            "role_name": "Powertrain",
            "is_finance": False,
            "status": "ACTIVE",
        }

    def test_refuses_invalid_cpf(self):
        team = ObjectGenerator.create_team()
        role_key = ObjectGenerator.create_role(team)
        payload = PayloadGenerator.create_member_payload(role_key, document_number="111.222.333-44")

        status, response = RequestGenerator.POST_member(team["team_key"], team["member_key"], payload)
        assert status == 422
        assert response["code"] == "PDK-MEMB-002"

    def test_refuses_duplicated_cpf_and_email_in_the_team(self):
        team = ObjectGenerator.create_team()
        role_key = ObjectGenerator.create_role(team)
        first = PayloadGenerator.create_member_payload(role_key)

        status, _response = RequestGenerator.POST_member(team["team_key"], team["member_key"], first)
        assert status == 201

        same_cpf = PayloadGenerator.create_member_payload(role_key, document_number=first["document_number"])
        status, response = RequestGenerator.POST_member(team["team_key"], team["member_key"], same_cpf)
        assert status == 409
        assert response["code"] == "PDK-MEMB-003"
        assert first["document_number"] not in response["description"]

        same_email = PayloadGenerator.create_member_payload(role_key, email=first["email"])
        status, response = RequestGenerator.POST_member(team["team_key"], team["member_key"], same_email)
        assert status == 409
        assert response["code"] == "PDK-MEMB-004"

    def test_same_cpf_in_two_teams(self):
        """O CPF é único por equipe: a mesma pessoa pode ser responsável em duas."""
        team = ObjectGenerator.create_team()
        other_team = ObjectGenerator.create_team()

        payload = PayloadGenerator.create_member_payload(ObjectGenerator.create_role(team))
        status, _response = RequestGenerator.POST_member(team["team_key"], team["member_key"], payload)
        assert status == 201

        payload["role_key"] = ObjectGenerator.create_role(other_team)
        status, _response = RequestGenerator.POST_member(other_team["team_key"], other_team["member_key"], payload)
        assert status == 201

    def test_role_from_body_missing_or_from_another_team(self):
        team = ObjectGenerator.create_team()
        other_team = ObjectGenerator.create_team()

        status, response = RequestGenerator.POST_member(
            team["team_key"], team["member_key"], PayloadGenerator.create_member_payload(UNKNOWN_KEY)
        )
        assert status == 404
        assert response["code"] == "PDK-ROLE-001"

        foreign_role_key = ObjectGenerator.create_role(other_team)
        status, response = RequestGenerator.POST_member(
            team["team_key"], team["member_key"], PayloadGenerator.create_member_payload(foreign_role_key)
        )
        assert status == 422
        assert response["code"] == "PDK-GEN-003"

    def test_finance_role_changes_only_by_handover(self):
        """Nem o cadastro nem o PATCH põem ou tiram alguém do cargo financeiro."""
        team = ObjectGenerator.create_team()
        common_role_key = ObjectGenerator.create_role(team)
        common_member_key = ObjectGenerator.create_member(team, common_role_key)

        status, response = RequestGenerator.POST_member(
            team["team_key"], team["member_key"], PayloadGenerator.create_member_payload(team["finance_role_key"])
        )
        assert status == 409
        assert response["code"] == "PDK-ROLE-004"

        status, response = RequestGenerator.PATCH_member(
            common_member_key, team["member_key"], {"role_key": team["finance_role_key"]}
        )
        assert status == 409
        assert response["code"] == "PDK-ROLE-004"

        status, response = RequestGenerator.PATCH_member(
            team["member_key"], team["member_key"], {"role_key": common_role_key}
        )
        assert status == 409
        assert response["code"] == "PDK-ROLE-004"

    def test_updates_contact_and_role(self):
        team = ObjectGenerator.create_team()
        member_key = ObjectGenerator.create_member(team)
        new_role_key = ObjectGenerator.create_role(team, name="Eletrônica")

        status, response = RequestGenerator.PATCH_member(
            member_key, team["member_key"], {"phone": "+55 11 98888-7777", "role_key": new_role_key}
        )
        assert status == 200
        assert response["phone"] == "+55 11 98888-7777"
        assert response["role_key"] == new_role_key
        assert response["role_name"] == "Eletrônica"

    def test_refuses_email_of_another_member(self):
        team = ObjectGenerator.create_team()
        first = PayloadGenerator.create_member_payload(ObjectGenerator.create_role(team))
        status, _response = RequestGenerator.POST_member(team["team_key"], team["member_key"], first)
        assert status == 201

        member_key = ObjectGenerator.create_member(team)

        status, response = RequestGenerator.PATCH_member(member_key, team["member_key"], {"email": first["email"]})
        assert status == 409
        assert response["code"] == "PDK-MEMB-004"

    def test_inactive_member_cannot_act(self):
        """Desativado, o responsável deixa de agir — inclusive de ler."""
        team = ObjectGenerator.create_team()
        member_key = ObjectGenerator.create_member(team)

        status, _response = RequestGenerator.GET_team(team["team_key"], member_key)
        assert status == 200

        status, response = RequestGenerator.PATCH_member(member_key, team["member_key"], {"active": False})
        assert status == 200
        assert response["status"] == "INACTIVE"

        status, response = RequestGenerator.GET_team(team["team_key"], member_key)
        assert status == 422
        assert response["code"] == "PDK-MEMB-005"

        status, response = RequestGenerator.PATCH_member(member_key, team["member_key"], {"active": True})
        assert status == 200
        assert response["status"] == "ACTIVE"

        status, _response = RequestGenerator.GET_team(team["team_key"], member_key)
        assert status == 200

    def test_finance_member_cannot_be_deactivated(self):
        team = ObjectGenerator.create_team()

        status, response = RequestGenerator.PATCH_member(team["member_key"], team["member_key"], {"active": False})
        assert status == 409
        assert response["code"] == "PDK-MEMB-006"

    def test_only_finance_manages_members(self):
        team = ObjectGenerator.create_team()
        role_key = ObjectGenerator.create_role(team)
        common_member_key = ObjectGenerator.create_member(team, role_key)

        status, response = RequestGenerator.POST_member(
            team["team_key"], common_member_key, PayloadGenerator.create_member_payload(role_key)
        )
        assert status == 403
        assert response["code"] == "PDK-GEN-004"

        status, response = RequestGenerator.PATCH_member(common_member_key, common_member_key, {"name": "Outro Nome"})
        assert status == 403
        assert response["code"] == "PDK-GEN-004"

    def test_member_of_another_team_looks_like_it_does_not_exist(self):
        team = ObjectGenerator.create_team()
        intruder = ObjectGenerator.create_team()

        status, response = RequestGenerator.GET_member(team["member_key"], intruder["member_key"])
        assert status == 404
        assert response["code"] == "PDK-MEMB-001"

        status, response = RequestGenerator.PATCH_member(team["member_key"], intruder["member_key"], {"name": "X"})
        assert status == 404
        assert response["code"] == "PDK-MEMB-001"

        status, response = RequestGenerator.GET_members(team["team_key"], intruder["member_key"])
        assert status == 404
        assert response["code"] == "PDK-TEAM-001"

    def test_lists_and_filters_by_role(self):
        team = ObjectGenerator.create_team()
        role_key = ObjectGenerator.create_role(team)
        first_key = ObjectGenerator.create_member(team, role_key)
        second_key = ObjectGenerator.create_member(team, role_key)

        status, response = RequestGenerator.GET_members(team["team_key"], team["member_key"])
        assert status == 200
        assert len(response["data"]) == 3
        assert response["is_last_page"] is True

        status, response = RequestGenerator.GET_members(team["team_key"], team["member_key"], {"role_key": role_key})
        assert status == 200
        listed_keys = []
        for member in response["data"]:
            listed_keys.append(member["member_key"])
        assert listed_keys == [second_key, first_key]

        status, response = RequestGenerator.GET_members(
            team["team_key"], team["member_key"], {"role_key": UNKNOWN_KEY}
        )
        assert status == 404
        assert response["code"] == "PDK-ROLE-001"

        status, response = RequestGenerator.GET_members(team["team_key"], team["member_key"], {"cargo": role_key})
        assert status == 400
        assert response["code"] == "PDK-GEN-001"
