from sqlalchemy import BigInteger, CHAR, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import relationship
from models.base import Base
from models import Account, Member


class Loan(Base):
    """Um crédito contratado pela equipe.

    A taxa (`monthly_rate_bps`) é COPIADA do plano na contratação: trocar
    de plano depois não muda um crédito que já existe. O valor de cada
    parcela (`installment_amount`) sai da tabela Price e também fica
    gravado, pra que ninguém precise refazer a conta.

    O status é derivado das parcelas: PAID quando todas foram pagas,
    LATE quando alguma está em atraso, ACTIVE nos outros casos.
    """

    __tablename__ = "loan"

    id = Column(Integer, primary_key=True)
    loan_key = Column(CHAR(36), nullable=False)
    account_id = Column(Integer, ForeignKey(Account.id), nullable=False)
    requester_member_id = Column(Integer, ForeignKey(Member.id), nullable=False)
    status = Column(String(20), nullable=False)
    principal = Column(BigInteger, nullable=False)
    monthly_rate_bps = Column(Integer, nullable=False)
    installments = Column(Integer, nullable=False)
    installment_amount = Column(BigInteger, nullable=False)
    purpose = Column(String(255), nullable=False)
    idempotency_key = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("loan_key"),
        UniqueConstraint("account_id", "idempotency_key"),
    )

    ACTIVE = "ACTIVE"
    LATE = "LATE"
    PAID = "PAID"

    account = relationship("Account", foreign_keys=[account_id])
    requester = relationship("Member", foreign_keys=[requester_member_id], lazy="selectin")

    installment_list = relationship(
        "LoanInstallment",
        back_populates="loan",
        order_by="asc(LoanInstallment.number)",
    )
