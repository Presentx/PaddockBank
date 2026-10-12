from tests.utils import ObjectGenerator, PayloadGenerator, RequestGenerator


class TestSupplier:
    def test_any_active_member_creates_supplier(self):
        """Cadastrar fornecedor não exige o cargo financeiro: quem compra conhece a loja."""
        team = ObjectGenerator.create_team()
        common_member_key = ObjectGenerator.create_member(team)
        payload = PayloadGenerator.create_supplier_payload()

        status, response = RequestGenerator.POST_supplier(team["team_key"], common_member_key, payload)
        assert status == 201
        supplier_key = response["supplier_key"]

        status, response = RequestGenerator.GET_suppliers(team["team_key"], common_member_key)
        assert status == 200
        assert response["data"] == [
            {
                "supplier_key": supplier_key,
                "name": payload["name"],
                "document_number": payload["document_number"],
                "pix_key": payload["pix_key"],
            }
        ]
        assert response["is_last_page"] is True

    def test_refuses_invalid_cnpj(self):
        """Máscara certa e dígitos verificadores errados: 422, e não 400."""
        team = ObjectGenerator.create_team()

        for invalid_cnpj in ["11.222.333/0001-00", "11.111.111/1111-11"]:
            payload = PayloadGenerator.create_supplier_payload(document_number=invalid_cnpj)

            status, response = RequestGenerator.POST_supplier(team["team_key"], team["member_key"], payload)
            assert status == 422, f"CNPJ '{invalid_cnpj}' foi aceito"
            assert response["code"] == "PDK-SUPP-002"

    def test_schema_refuses_cnpj_without_mask(self):
        team = ObjectGenerator.create_team()
        payload = PayloadGenerator.create_supplier_payload(document_number="11222333000181")

        status, response = RequestGenerator.POST_supplier(team["team_key"], team["member_key"], payload)
        assert status == 400
        assert response["code"] == "PDK-GEN-001"

    def test_refuses_duplicated_cnpj_in_the_team(self):
        team = ObjectGenerator.create_team()
        other_team = ObjectGenerator.create_team()
        payload = PayloadGenerator.create_supplier_payload()

        status, _response = RequestGenerator.POST_supplier(team["team_key"], team["member_key"], payload)
        assert status == 201

        status, response = RequestGenerator.POST_supplier(team["team_key"], team["member_key"], payload)
        assert status == 409
        assert response["code"] == "PDK-SUPP-003"

        # O mesmo CNPJ em OUTRA equipe não é conflito.
        status, _response = RequestGenerator.POST_supplier(other_team["team_key"], other_team["member_key"], payload)
        assert status == 201

    def test_team_of_another_member_looks_like_it_does_not_exist(self):
        team = ObjectGenerator.create_team()
        intruder = ObjectGenerator.create_team()

        status, response = RequestGenerator.POST_supplier(
            team["team_key"], intruder["member_key"], PayloadGenerator.create_supplier_payload()
        )
        assert status == 404
        assert response["code"] == "PDK-TEAM-001"

        status, response = RequestGenerator.GET_suppliers(team["team_key"], intruder["member_key"])
        assert status == 404
        assert response["code"] == "PDK-TEAM-001"
