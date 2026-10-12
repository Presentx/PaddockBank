from uuid import uuid4

from tests.utils.random_generator import RandomGenerator


class PayloadGenerator:
    """Corpos válidos de cada POST, com qualquer campo trocado a pedido.

    Sem argumento, tudo o que precisa ser único sai aleatório (nome da
    equipe, CPF, CNPJ, e-mail, chave de idempotência), pra que dois
    cadastros seguidos não batam numa regra de duplicidade.
    """

    @staticmethod
    def create_sample_entity_payload(
        hello: str = None,
        name: str = None,
        email: str = None,
        document_number: str = None,
        birthdate: str = None,
    ) -> dict:
        """Um cadastro valido, com qualquer campo trocado a pedido.

        Sem argumento nenhum o payload sai aleatorio no que precisa ser
        unico (e-mail e CPF), pra que dois cadastros seguidos nao batam
        na regra de duplicidade. Quem testa FILTRO precisa do contrario
        disso: um valor conhecido, pra poder procurar por ele depois.
        """
        if hello is None:
            hello = "world"

        if name is None:
            name = "Maria da Silva"

        if email is None:
            email = f"maria.silva.{uuid4()}@exemplo.com.br"

        if document_number is None:
            document_number = RandomGenerator.generate_cpf()

        if birthdate is None:
            birthdate = "1990-05-17"

        payload = {
            "hello": hello,
            "name": name,
            "email": email,
            "document_number": document_number,
            "birthdate": birthdate,
        }
        return payload

    @staticmethod
    def create_new_status_payload(new_status: str = None) -> dict:
        payload = {"status": new_status}
        return payload

    @staticmethod
    def create_member_fields(name: str = None, document_number: str = None, email: str = None) -> dict:
        if name is None:
            name = "Ayrton da Silva"

        if document_number is None:
            document_number = RandomGenerator.generate_cpf()

        if email is None:
            email = f"member-{uuid4().hex[:12]}@example.com"

        return {
            "name": name,
            "document_number": document_number,
            "email": email,
            "phone": "+55 16 99999-0000",
            "pix_key": email,
        }

    @staticmethod
    def create_team_payload(name: str = None, university: str = None, treasurer: dict = None) -> dict:
        if name is None:
            name = f"Formula {uuid4().hex[:10]}"

        if university is None:
            university = "USP São Carlos"

        if treasurer is None:
            treasurer = PayloadGenerator.create_member_fields()

        return {
            "name": name,
            "university": university,
            "finance_role_name": "Diretoria Financeira",
            "treasurer": treasurer,
        }

    @staticmethod
    def create_role_payload(name: str = None, parent_role_key: str = None) -> dict:
        if name is None:
            name = f"Cargo {uuid4().hex[:8]}"

        payload = {"name": name}

        if parent_role_key is not None:
            payload["parent_role_key"] = parent_role_key

        return payload

    @staticmethod
    def create_member_payload(role_key: str, **fields) -> dict:
        payload = PayloadGenerator.create_member_fields(**fields)
        payload["role_key"] = role_key

        return payload

    @staticmethod
    def create_supplier_payload(document_number: str = None) -> dict:
        if document_number is None:
            document_number = RandomGenerator.generate_cnpj()

        return {
            "name": "Usinagem Interlagos Ltda",
            "document_number": document_number,
            "pix_key": document_number,
        }

    @staticmethod
    def create_subsystem_payload(owner_role_key: str, budget: int = 100000, name: str = None) -> dict:
        if name is None:
            name = f"Powertrain {uuid4().hex[:8]}"

        return {"name": name, "budget": budget, "owner_role_key": owner_role_key}

    @staticmethod
    def create_deposit_payload(amount: int, idempotency_key: str = None) -> dict:
        if idempotency_key is None:
            idempotency_key = uuid4().hex

        return {
            "amount": amount,
            "payer_name": "Patrocinador Master S.A.",
            "payer_document": RandomGenerator.generate_cnpj(),
            "description": "Cota de patrocínio",
            "idempotency_key": idempotency_key,
        }

    @staticmethod
    def create_expense_payload(
        subsystem_key: str,
        supplier_key: str,
        amount: int = 15000,
        kind: str = "SUPPLIER_PAYMENT",
        invoice_number: str = None,
        idempotency_key: str = None,
    ) -> dict:
        if idempotency_key is None:
            idempotency_key = uuid4().hex

        payload = {
            "subsystem_key": subsystem_key,
            "supplier_key": supplier_key,
            "kind": kind,
            "amount": amount,
            "description": "Jogo de pastilhas de freio",
            "idempotency_key": idempotency_key,
        }

        if invoice_number is not None:
            payload["invoice_number"] = invoice_number

        return payload

    @staticmethod
    def create_loan_payload(amount: int, installments: int = 3, idempotency_key: str = None) -> dict:
        if idempotency_key is None:
            idempotency_key = uuid4().hex

        return {
            "amount": amount,
            "installments": installments,
            "purpose": "Estoque de camisetas da equipe",
            "idempotency_key": idempotency_key,
        }

    @staticmethod
    def create_handover_payload(incoming_member_key: str, outgoing_role_key: str, idempotency_key: str = None) -> dict:
        if idempotency_key is None:
            idempotency_key = uuid4().hex

        return {
            "incoming_member_key": incoming_member_key,
            "outgoing_role_key": outgoing_role_key,
            "idempotency_key": idempotency_key,
        }
