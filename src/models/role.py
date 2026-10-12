from sqlalchemy import Boolean, CHAR, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import relationship
from models.base import Base
from models import Team


class Role(Base):
    """Um cargo da equipe — um nó da árvore de cargos.

    A árvore é a própria tabela apontando pra si: `parent_role_id` é o
    cargo superior, e nulo quer dizer raiz. Ela é mutável (dá pra
    renomear e reposicionar), porque a diretoria de uma equipe muda todo
    ano e o banco não pode impor um organograma.

    `is_finance` marca o cargo financeiro: ele nasce com a equipe, tem
    nome livre, e quem o ocupa é o titular da conta. Existe exatamente
    um por equipe — quem garante é o índice único parcial
    `role_one_finance_per_team`, no database/database.sql.
    """

    __tablename__ = "role"

    id = Column(Integer, primary_key=True)
    role_key = Column(CHAR(36), nullable=False)
    team_id = Column(Integer, ForeignKey(Team.id), nullable=False)
    parent_role_id = Column(Integer, ForeignKey("role.id"), nullable=True)
    name = Column(String(255), nullable=False)
    is_finance = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("role_key"),
        UniqueConstraint("team_id", "name"),
    )

    parent = relationship("Role", remote_side=[id], foreign_keys=[parent_role_id])
