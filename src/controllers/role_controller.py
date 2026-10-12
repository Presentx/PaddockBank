from controllers.base_controller import BaseController
from dtos import RoleDTO
from errors import DuplicatedRoleName, InvalidParentRole, NotFoundRole, NotFoundTeam
from models import Member, Role, Team
from repositories import RoleRepository, TeamRepository
from utils.pagination import split_page


class RoleController(BaseController):
    """As regras de negócio dos cargos — a árvore que organiza a equipe."""

    def __init__(self) -> None:
        super().__init__(__name__)
        self.role_repository = RoleRepository(self.context)
        self.team_repository = TeamRepository(self.context)

    def create(self, team_key: str, role_data: dict) -> dict:
        """Cria um cargo comum. O cargo financeiro não nasce aqui: nasce com a equipe."""
        actor = self._get_actor()
        self._require_finance(actor)
        team = self._get_team(actor, team_key)

        name = role_data["name"]
        parent = None

        if role_data.get("parent_role_key") is not None:
            parent = self._get_referenced_role(actor, role_data["parent_role_key"], "parent_role_key")

        if self.role_repository.get_by_name(team.id, name) is not None:
            raise DuplicatedRoleName(name)

        role = self.role_repository.create(team, name, parent=parent)

        self._flush_or_conflict({"role_team_name_key": DuplicatedRoleName(name)})

        role_dto = RoleDTO.only_obj_key(role)
        self.session.commit()

        return role_dto

    def update(self, role_key: str, role_data: dict) -> dict:
        """Renomeia ou reposiciona um cargo — inclusive o financeiro.

        Renomear o cargo financeiro é permitido (o nome dele é livre:
        "Tesouraria", "Diretoria Financeira"...). O que NÃO muda por
        aqui é quem o ocupa: isso é a passagem de gestão.

        `parent_role_key: null` leva o cargo pra raiz da árvore.
        """
        actor = self._get_actor()
        self._require_finance(actor)
        role = self._get_role(actor, role_key)

        if "name" in role_data and role_data["name"] != role.name:
            name = role_data["name"]

            if self.role_repository.get_by_name(role.team_id, name) is not None:
                raise DuplicatedRoleName(name)

            self.role_repository.update_name(role, name)

        if "parent_role_key" in role_data:
            parent = None

            if role_data["parent_role_key"] is not None:
                parent = self._get_referenced_role(actor, role_data["parent_role_key"], "parent_role_key")
                self._check_parent_is_not_subordinate(role, parent)

            self.role_repository.update_parent(role, parent)

        self._flush_or_conflict({"role_team_name_key": DuplicatedRoleName(role_data.get("name"))})

        role_dto = RoleDTO.obj_to_dict(role)
        self.session.commit()

        return role_dto

    def get_list(self, team_key: str, limit: int, offset: int) -> dict:
        actor = self._get_actor()
        team = self._get_team(actor, team_key)

        roles_list, is_last_page = split_page(self.role_repository.list_page(team.id, limit, offset), limit)

        return {
            "data": RoleDTO.list_obj_to_list_dict(roles_list),
            "is_last_page": is_last_page,
        }

    def _check_parent_is_not_subordinate(self, role: Role, parent: Role) -> None:
        """Recusa o cargo superior que criaria um ciclo na árvore.

        Sobe da candidata a superior até a raiz. Se o próprio cargo
        aparecer no caminho, a candidata é ele mesmo ou está ABAIXO dele
        — e pô-la acima dele fecharia um círculo: um cargo que é
        superior do próprio superior.

        O limite de passos é só um cinto de segurança: a árvore não tem
        ciclos (este método é quem garante), então a subida sempre
        termina na raiz.
        """
        current = parent
        steps = 0

        while current is not None and steps < 1000:
            if current.id == role.id:
                raise InvalidParentRole()

            current = current.parent
            steps = steps + 1

    def _get_team(self, actor: Member, team_key: str) -> Team:
        team = self.team_repository.get_by_key(team_key)

        if team is None or team.id != actor.team_id:
            raise NotFoundTeam(team_key)

        return team

    def _get_role(self, actor: Member, role_key: str) -> Role:
        """O cargo do CAMINHO: de outra equipe, responde o mesmo 404 de "não existe"."""
        role = self.role_repository.get_by_key(role_key)

        if role is None or role.team_id != actor.team_id:
            raise NotFoundRole(role_key)

        return role

    def _get_referenced_role(self, actor: Member, role_key: str, field: str) -> Role:
        """O cargo citado no CORPO: não existe é 404; de outra equipe é 422."""
        role = self.role_repository.get_by_key(role_key)

        if role is None:
            raise NotFoundRole(role_key)

        self._require_same_team(actor, role.team_id, field)

        return role
