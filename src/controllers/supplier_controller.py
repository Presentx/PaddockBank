from controllers.base_controller import BaseController
from dtos import SupplierDTO
from errors import DuplicatedSupplierDocument, InvalidCnpj, NotFoundTeam
from models import Member, Team
from repositories import SupplierRepository, TeamRepository
from utils.document_number import is_valid_cnpj
from utils.pagination import split_page


class SupplierController(BaseController):
    """As regras de negócio dos fornecedores.

    Qualquer responsável ativo cadastra fornecedor — quem compra a peça
    é quem conhece a loja. O que protege o dinheiro não é restringir o
    cadastro: é que cadastrar não paga ninguém. Todo pagamento ainda
    passa pela aprovação do financeiro.
    """

    def __init__(self) -> None:
        super().__init__(__name__)
        self.supplier_repository = SupplierRepository(self.context)
        self.team_repository = TeamRepository(self.context)

    def create(self, team_key: str, supplier_data: dict) -> dict:
        actor = self._get_actor()
        team = self._get_team(actor, team_key)

        document_number = supplier_data["document_number"]

        if not is_valid_cnpj(document_number):
            raise InvalidCnpj()

        if self.supplier_repository.get_by_document_number(team.id, document_number) is not None:
            raise DuplicatedSupplierDocument()

        supplier = self.supplier_repository.create(team, supplier_data)

        self._flush_or_conflict({"supplier_team_document_number_key": DuplicatedSupplierDocument()})

        supplier_dto = SupplierDTO.only_obj_key(supplier)
        self.session.commit()

        return supplier_dto

    def get_list(self, team_key: str, limit: int, offset: int) -> dict:
        actor = self._get_actor()
        team = self._get_team(actor, team_key)

        suppliers_list, is_last_page = split_page(self.supplier_repository.list_page(team.id, limit, offset), limit)

        return {
            "data": SupplierDTO.list_obj_to_list_dict(suppliers_list),
            "is_last_page": is_last_page,
        }

    def _get_team(self, actor: Member, team_key: str) -> Team:
        team = self.team_repository.get_by_key(team_key)

        if team is None or team.id != actor.team_id:
            raise NotFoundTeam(team_key)

        return team
