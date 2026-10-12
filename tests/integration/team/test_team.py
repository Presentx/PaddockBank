from tests.utils import ObjectGenerator, PayloadGenerator, RequestGenerator

UNKNOWN_KEY = "00000000-0000-0000-0000-000000000000"


class TestTeam:
    def test_creates_team_with_account_role_and_treasurer(self):
        """Um POST cria a equipe, a conta, o cargo financeiro e o responsável."""
        payload = PayloadGenerator.create_team_payload()

        status, created = RequestGenerator.POST_team(payload)
        assert status == 201
        assert sorted(created.keys()) == ["account_key", "finance_role_key", "member_key", "pix_key", "team_key"]

        status, team = RequestGenerator.GET_team(created["team_key"], created["member_key"])
        assert status == 200
        assert team["name"] == payload["name"]
        assert team["university"] == payload["university"]
        assert team["account"] == {
            "account_key": created["account_key"],
            "pix_key": created["pix_key"],
            "plan": "FREE",
        }
        assert team["finance_member"]["member_key"] == created["member_key"]
        assert team["finance_member"]["role_key"] == created["finance_role_key"]
        assert team["finance_member"]["role_name"] == "Diretoria Financeira"

        status, account = RequestGenerator.GET_account(created["account_key"], created["member_key"])
        assert status == 200
        assert account["balance"] == 0
        assert account["plan"] == "FREE"
        assert account["outgoing_fee_bps"] == 100
        assert account["holder"]["member_key"] == created["member_key"]
        assert account["available_credit_limit"] == 0
        assert account["open_loans"] == []

    def test_refuses_duplicated_name_and_university(self):
        """Repetir o cadastro não cria outra equipe: 409, e nada novo nasce."""
        payload = PayloadGenerator.create_team_payload()

        status, _response = RequestGenerator.POST_team(payload)
        assert status == 201

        payload["treasurer"] = PayloadGenerator.create_member_fields()

        status, response = RequestGenerator.POST_team(payload)
        assert status == 409
        assert response["code"] == "PDK-TEAM-002"

    def test_same_name_in_another_university_is_another_team(self):
        payload = PayloadGenerator.create_team_payload()

        status, _response = RequestGenerator.POST_team(payload)
        assert status == 201

        other = PayloadGenerator.create_team_payload(name=payload["name"], university="UNICAMP")

        status, _response = RequestGenerator.POST_team(other)
        assert status == 201

    def test_refuses_invalid_cpf(self):
        """Máscara certa e dígitos verificadores errados: 422, sem o CPF na mensagem."""
        treasurer = PayloadGenerator.create_member_fields(document_number="111.222.333-44")

        status, response = RequestGenerator.POST_team(PayloadGenerator.create_team_payload(treasurer=treasurer))
        assert status == 422
        assert response["code"] == "PDK-MEMB-002"
        assert "111.222.333-44" not in response["description"]

    def test_schema_refuses_malformed_body(self):
        status, response = RequestGenerator.POST_team({})
        assert status == 400
        assert response["code"] == "PDK-GEN-001"

        payload = PayloadGenerator.create_team_payload()
        payload["treasurer"]["document_number"] = "11122233344"

        status, response = RequestGenerator.POST_team(payload)
        assert status == 400
        assert response["code"] == "PDK-GEN-001"

    def test_schema_refuses_actor_in_the_body(self):
        """Nenhum corpo aceita dizer quem está agindo: campo a mais é 400."""
        payload = PayloadGenerator.create_team_payload()
        payload["member_key"] = UNKNOWN_KEY

        status, response = RequestGenerator.POST_team(payload)
        assert status == 400
        assert response["code"] == "PDK-GEN-001"

    def test_get_without_identity(self):
        """Com o token e sem identidade: 401, e não 403."""
        team = ObjectGenerator.create_team()

        status, response = RequestGenerator.GET_team(team["team_key"])
        assert status == 401
        assert response["code"] == "PDK-GEN-006"

        status, response = RequestGenerator.GET_team(team["team_key"], UNKNOWN_KEY)
        assert status == 401
        assert response["code"] == "PDK-GEN-006"

        status, response = RequestGenerator.GET_team(team["team_key"], "isto-nao-e-uma-chave")
        assert status == 401
        assert response["code"] == "PDK-GEN-006"

    def test_team_of_another_member_looks_like_it_does_not_exist(self):
        """IDOR: a equipe dos outros responde o MESMO 404 de uma chave inventada."""
        team = ObjectGenerator.create_team()
        intruder = ObjectGenerator.create_team()

        status, foreign = RequestGenerator.GET_team(team["team_key"], intruder["member_key"])
        assert status == 404
        assert foreign["code"] == "PDK-TEAM-001"

        status, missing = RequestGenerator.GET_team(UNKNOWN_KEY, intruder["member_key"])
        assert status == 404
        assert missing["code"] == "PDK-TEAM-001"
        assert foreign["title"] == missing["title"]
