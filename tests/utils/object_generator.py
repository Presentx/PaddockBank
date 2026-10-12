from tests.utils.payload_generator import PayloadGenerator
from tests.utils.request_generator import RequestGenerator


class ObjectGenerator:
    """Cria pela API o que o teste precisa ter pronto antes de começar.

    Tudo nasce por POST, como um cliente faria. Cada teste começa por
    `create_team()`, que devolve uma equipe NOVA: como todo recurso
    deste sistema pertence a uma equipe, um teste que cria a própria
    não enxerga nada do que os outros deixaram no banco — e por isso
    nenhum deles precisa zerá-lo.
    """

    @staticmethod
    def create_sample_entity(hello: str = None) -> dict:

        sample_entity_payload = PayloadGenerator.create_sample_entity_payload(hello=hello)

        status, response = RequestGenerator.POST_sample_entity(sample_entity_payload)
        assert status == 201

        return response

    @staticmethod
    def update_sample_entity(sample_entity_key, new_status: str = None) -> dict:

        sample_entity_payload = PayloadGenerator.create_new_status_payload(new_status)

        status, response = RequestGenerator.PUT_sample_entity(sample_entity_key, sample_entity_payload)
        assert status == 202

        return response

    @staticmethod
    def create_team() -> dict:
        """Uma equipe recém-cadastrada.

        Devolve as cinco chaves da resposta do POST /team. A
        `member_key` é a do responsável FINANCEIRO: é com ela que o
        teste age quando precisa do cargo financeiro.
        """
        status, response = RequestGenerator.POST_team(PayloadGenerator.create_team_payload())
        assert status == 201

        return response

    @staticmethod
    def create_role(team: dict, parent_role_key: str = None, name: str = None) -> str:
        payload = PayloadGenerator.create_role_payload(name=name, parent_role_key=parent_role_key)

        status, response = RequestGenerator.POST_role(team["team_key"], team["member_key"], payload)
        assert status == 201

        return response["role_key"]

    @staticmethod
    def create_member(team: dict, role_key: str = None) -> str:
        """Um responsável comum (não financeiro). Sem `role_key`, ganha um cargo novo."""
        if role_key is None:
            role_key = ObjectGenerator.create_role(team)

        payload = PayloadGenerator.create_member_payload(role_key)

        status, response = RequestGenerator.POST_member(team["team_key"], team["member_key"], payload)
        assert status == 201

        return response["member_key"]

    @staticmethod
    def create_supplier(team: dict) -> str:
        payload = PayloadGenerator.create_supplier_payload()

        status, response = RequestGenerator.POST_supplier(team["team_key"], team["member_key"], payload)
        assert status == 201

        return response["supplier_key"]

    @staticmethod
    def create_subsystem(team: dict, budget: int = 100000) -> str:
        payload = PayloadGenerator.create_subsystem_payload(team["finance_role_key"], budget=budget)

        status, response = RequestGenerator.POST_subsystem(team["team_key"], team["member_key"], payload)
        assert status == 201

        return response["subsystem_key"]

    @staticmethod
    def deposit(team: dict, amount: int) -> dict:
        status, response = RequestGenerator.POST_deposit(
            team["pix_key"], PayloadGenerator.create_deposit_payload(amount)
        )
        assert status == 201

        return response

    @staticmethod
    def create_expense(team: dict, subsystem_key: str, supplier_key: str, member_key: str = None, **fields) -> str:
        """Um pedido PENDING. Sem `member_key`, quem solicita é o financeiro."""
        if member_key is None:
            member_key = team["member_key"]

        payload = PayloadGenerator.create_expense_payload(subsystem_key, supplier_key, **fields)

        status, response = RequestGenerator.POST_expense(member_key, payload)
        assert status == 201

        return response["expense_key"]
