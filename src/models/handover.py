from sqlalchemy import BigInteger, CHAR, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import relationship
from models.base import Base
from models import Account, Member, Transaction


class Handover(Base):
    """Uma passagem de gestão: quem deixou e quem assumiu o cargo financeiro.

    É o registro que sobrevive à troca anual de diretoria — a dor que o
    Paddock Bank existe pra resolver. Cada linha diz quem saiu, quem
    entrou, quanto foi cobrado e qual requisição causou a troca.

    `transaction_id` aponta pra linha HANDOVER_FEE do extrato, e fica
    nulo quando a passagem foi isenta (plano PRO ou carência).

    A `idempotency_key` é única por conta: repetir a passagem devolve o
    resultado original, sem cobrar de novo e sem trocar os cargos de
    volta.
    """

    __tablename__ = "handover"

    id = Column(Integer, primary_key=True)
    handover_key = Column(CHAR(36), nullable=False)
    account_id = Column(Integer, ForeignKey(Account.id), nullable=False)
    outgoing_member_id = Column(Integer, ForeignKey(Member.id), nullable=False)
    incoming_member_id = Column(Integer, ForeignKey(Member.id), nullable=False)
    fee = Column(BigInteger, nullable=False)
    transaction_id = Column(Integer, ForeignKey(Transaction.id), nullable=True)
    idempotency_key = Column(String(64), nullable=False)
    request_id = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("handover_key"),
        UniqueConstraint("account_id", "idempotency_key"),
    )

    account = relationship("Account", foreign_keys=[account_id])
    outgoing_member = relationship("Member", foreign_keys=[outgoing_member_id], lazy="selectin")
    incoming_member = relationship("Member", foreign_keys=[incoming_member_id], lazy="selectin")
    transaction = relationship("Transaction", foreign_keys=[transaction_id], lazy="selectin")
