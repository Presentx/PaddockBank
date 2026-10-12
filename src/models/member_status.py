from sqlalchemy import Column, DateTime, Integer, String, UniqueConstraint, func
from models.base import Base


class MemberStatus(Base):
    """A lista fechada de situações de um responsável.

    Não existe exclusão de responsável: quem sai da equipe passa a
    INACTIVE, e tudo o que ele solicitou ou aprovou continua apontando
    pra ele.
    """

    __tablename__ = "member_status"

    id = Column(Integer, primary_key=True)
    enumerator = Column(String(50), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (UniqueConstraint("enumerator"),)

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
