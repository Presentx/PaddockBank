from uuid import uuid4

from database import Context
from models import Role, Team


class RoleRepository:
    """As consultas dos cargos."""

    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def create(self, team: Team, name: str, parent: Role = None, is_finance: bool = False) -> Role:
        role = Role()

        role.role_key = str(uuid4())
        role.team_id = team.id
        role.name = name
        role.parent = parent
        role.is_finance = is_finance

        self.session.add(role)
        return role

    def update_name(self, role: Role, name: str) -> None:
        role.name = name

    def update_parent(self, role: Role, parent: Role) -> None:
        role.parent = parent

    def get_by_key(self, role_key: str) -> Role:
        return self.session.query(Role).filter(Role.role_key == role_key).first()

    def get_by_id(self, role_id: int) -> Role:
        return self.session.query(Role).filter(Role.id == role_id).first()

    def get_by_name(self, team_id: int, name: str) -> Role:
        return self.session.query(Role).filter(Role.team_id == team_id, Role.name == name).first()

    def get_finance_role(self, team_id: int) -> Role:
        return self.session.query(Role).filter(Role.team_id == team_id, Role.is_finance.is_(True)).first()

    def list_page(self, team_id: int, limit: int, offset: int) -> list:
        """A página pedida, na ordem em que os cargos foram criados.

        Ordem crescente, ao contrário das outras listagens: numa árvore,
        o cargo superior costuma nascer antes do subordinado, e ler de
        cima pra baixo é ler da raiz pras folhas.
        """
        query = self.session.query(Role).filter(Role.team_id == team_id).order_by(Role.id.asc())

        return query.limit(limit + 1).offset(offset).all()
