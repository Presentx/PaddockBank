from controllers.base_controller import BaseController
from dtos import SubsystemDTO
from errors import BudgetBelowCommitted, DuplicatedSubsystemName, NotFoundRole, NotFoundSubsystem, NotFoundTeam
from models import Member, Role, Team
from repositories import RoleRepository, SubsystemRepository, TeamRepository
from utils.pagination import split_page


class SubsystemController(BaseController):
    """As regras de negócio dos subsistemas — as fatias do orçamento.

    Criar e alterar é do financeiro. A regra que mais importa daqui, a
    RESERVA do orçamento, não mora neste arquivo: ela acontece quando
    alguém solicita um gasto (veja o ExpenseController.create).
    """

    def __init__(self) -> None:
        super().__init__(__name__)
        self.subsystem_repository = SubsystemRepository(self.context)
        self.role_repository = RoleRepository(self.context)
        self.team_repository = TeamRepository(self.context)

    def create(self, team_key: str, subsystem_data: dict) -> dict:
        actor = self._get_actor()
        self._require_finance(actor)
        team = self._get_team(actor, team_key)

        name = subsystem_data["name"]
        owner_role = self._get_referenced_role(actor, subsystem_data["owner_role_key"])

        if self.subsystem_repository.get_by_name(team.id, name) is not None:
            raise DuplicatedSubsystemName(name)

        subsystem = self.subsystem_repository.create(team, name, subsystem_data["budget"], owner_role)

        self._flush_or_conflict({"subsystem_team_name_key": DuplicatedSubsystemName(name)})

        subsystem_dto = SubsystemDTO.only_obj_key(subsystem)
        self.session.commit()

        return subsystem_dto

    def update(self, subsystem_key: str, subsystem_data: dict) -> dict:
        """Altera nome, teto ou cargo responsável.

        O subsistema é TRAVADO antes de o teto ser conferido, pelo mesmo
        motivo da solicitação de gasto: "o teto novo cobre o que já está
        comprometido?" é uma leitura seguida de uma gravação. Sem a
        trava, um pedido poderia reservar orçamento entre as duas, e o
        teto cairia abaixo do comprometido. Com ela, o pedido espera — e
        já encontra o teto novo.
        """
        actor = self._get_actor()
        self._require_finance(actor)

        subsystem = self.subsystem_repository.get_by_key(subsystem_key)

        if subsystem is None or subsystem.team_id != actor.team_id:
            raise NotFoundSubsystem(subsystem_key)

        subsystem = self.subsystem_repository.get_by_id_for_update(subsystem.id)

        if "owner_role_key" in subsystem_data:
            owner_role = self._get_referenced_role(actor, subsystem_data["owner_role_key"])
            self.subsystem_repository.update_owner_role(subsystem, owner_role)

        if "name" in subsystem_data and subsystem_data["name"] != subsystem.name:
            name = subsystem_data["name"]

            if self.subsystem_repository.get_by_name(subsystem.team_id, name) is not None:
                raise DuplicatedSubsystemName(name)

            self.subsystem_repository.update_name(subsystem, name)

        if "budget" in subsystem_data:
            budget = subsystem_data["budget"]

            if budget < subsystem.committed:
                raise BudgetBelowCommitted(budget, subsystem.committed)

            self.subsystem_repository.update_budget(subsystem, budget)

        self._flush_or_conflict({"subsystem_team_name_key": DuplicatedSubsystemName(subsystem_data.get("name"))})

        subsystem_dto = SubsystemDTO.obj_to_dict(subsystem)
        self.session.commit()

        return subsystem_dto

    def get_list(self, team_key: str, limit: int, offset: int) -> dict:
        actor = self._get_actor()
        team = self._get_team(actor, team_key)

        subsystems_list, is_last_page = split_page(
            self.subsystem_repository.list_page(team.id, limit, offset), limit
        )

        return {
            "data": SubsystemDTO.list_obj_to_list_dict(subsystems_list),
            "is_last_page": is_last_page,
        }

    def _get_team(self, actor: Member, team_key: str) -> Team:
        team = self.team_repository.get_by_key(team_key)

        if team is None or team.id != actor.team_id:
            raise NotFoundTeam(team_key)

        return team

    def _get_referenced_role(self, actor: Member, role_key: str) -> Role:
        role = self.role_repository.get_by_key(role_key)

        if role is None:
            raise NotFoundRole(role_key)

        self._require_same_team(actor, role.team_id, "owner_role_key")

        return role
