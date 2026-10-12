from sqlalchemy import BigInteger, CHAR, CheckConstraint, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import relationship
from models.base import Base
from models import Role, Team


class Subsystem(Base):
    """Uma fatia do orçamento da equipe (powertrain, aerodinâmica, ...).

    `budget` é o teto; `committed` é o que já está comprometido — a soma
    dos pedidos PENDING e PAID do subsistema. O valor é reservado já na
    SOLICITAÇÃO do gasto, e só volta se o pedido for recusado ou
    cancelado.

    Diferente da lotação de uma estante, aqui o comprometido É uma
    coluna, e de propósito: ela é a linha que o POST /expense trava
    (`SELECT ... FOR UPDATE`) pra decidir se o pedido cabe, e o CHECK
    committed <= budget é a última barreira caso o código erre.
    """

    __tablename__ = "subsystem"

    id = Column(Integer, primary_key=True)
    subsystem_key = Column(CHAR(36), nullable=False)
    team_id = Column(Integer, ForeignKey(Team.id), nullable=False)
    owner_role_id = Column(Integer, ForeignKey(Role.id), nullable=False)
    name = Column(String(255), nullable=False)
    budget = Column(BigInteger, nullable=False)
    committed = Column(BigInteger, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("subsystem_key"),
        UniqueConstraint("team_id", "name"),
        CheckConstraint("budget >= 0"),
        CheckConstraint("committed >= 0 AND committed <= budget"),
    )

    owner_role = relationship("Role", foreign_keys=[owner_role_id], lazy="selectin")
