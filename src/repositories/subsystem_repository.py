from uuid import uuid4

from database import Context
from models import Role, Subsystem, Team


class SubsystemRepository:
    """As consultas dos subsistemas.

    O `get_by_id_for_update` é a peça que o ExpenseController usa pra
    decidir se um pedido cabe no orçamento sem ser atropelado por outro
    pedido. O porquê do `populate_existing` está no AccountRepository.
    """

    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def create(self, team: Team, name: str, budget: int, owner_role: Role) -> Subsystem:
        subsystem = Subsystem()

        subsystem.subsystem_key = str(uuid4())
        subsystem.team_id = team.id
        subsystem.name = name
        subsystem.budget = budget
        subsystem.committed = 0
        subsystem.owner_role = owner_role

        self.session.add(subsystem)
        return subsystem

    def update_name(self, subsystem: Subsystem, name: str) -> None:
        subsystem.name = name

    def update_budget(self, subsystem: Subsystem, budget: int) -> None:
        subsystem.budget = budget

    def update_owner_role(self, subsystem: Subsystem, owner_role: Role) -> None:
        subsystem.owner_role = owner_role

    def reserve(self, subsystem: Subsystem, amount: int) -> None:
        subsystem.committed = subsystem.committed + amount

    def release(self, subsystem: Subsystem, amount: int) -> None:
        subsystem.committed = subsystem.committed - amount

    def get_by_key(self, subsystem_key: str) -> Subsystem:
        return self.session.query(Subsystem).filter(Subsystem.subsystem_key == subsystem_key).first()

    def get_by_name(self, team_id: int, name: str) -> Subsystem:
        return self.session.query(Subsystem).filter(Subsystem.team_id == team_id, Subsystem.name == name).first()

    def get_by_id_for_update(self, subsystem_id: int) -> Subsystem:
        return (
            self.session.query(Subsystem)
            .filter(Subsystem.id == subsystem_id)
            .populate_existing()
            .with_for_update()
            .first()
        )

    def list_page(self, team_id: int, limit: int, offset: int) -> list:
        query = (
            self.session.query(Subsystem)
            .filter(Subsystem.team_id == team_id)
            .order_by(Subsystem.created_at.desc(), Subsystem.id.desc())
        )

        return query.limit(limit + 1).offset(offset).all()
