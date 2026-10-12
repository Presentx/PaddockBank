from sqlalchemy import CHAR, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import relationship
from models.base import Base
from models import MemberStatus, Role, Team


class Member(Base):
    """Um responsável da equipe: um CPF vinculado a um cargo.

    É ele o ATOR de toda operação com sessão: a `member_key` chega do
    gateway no cabeçalho X-Member-Key, e nunca no corpo (veja
    src/middlewares/member_identity.py).

    CPF e e-mail são únicos por equipe, não no banco inteiro: a mesma
    pessoa pode ser responsável em duas equipes.

    A `pix_key` daqui é a chave pessoal do responsável — é para ela que
    vai o reembolso de um gasto que ele pagou do próprio bolso.
    """

    __tablename__ = "member"

    id = Column(Integer, primary_key=True)
    member_key = Column(CHAR(36), nullable=False)
    team_id = Column(Integer, ForeignKey(Team.id), nullable=False)
    role_id = Column(Integer, ForeignKey(Role.id), nullable=False)
    status_id = Column(Integer, ForeignKey(MemberStatus.id), nullable=False)
    name = Column(String(255), nullable=False)
    document_number = Column(CHAR(14), nullable=False)
    email = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=False)
    pix_key = Column(String(77), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("member_key"),
        UniqueConstraint("team_id", "document_number"),
        UniqueConstraint("team_id", "email"),
    )

    role = relationship("Role", foreign_keys=[role_id], lazy="selectin")
    status = relationship("MemberStatus", foreign_keys=[status_id], lazy="selectin")
