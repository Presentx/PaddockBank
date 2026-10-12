from sqlalchemy import BigInteger, Column, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship
from models.base import Base
from models import Loan, Transaction


class LoanInstallment(Base):
    """Uma parcela de um crédito.

    PENDING até o vencimento; a cobrança diária a leva a PAID (com
    saldo) ou a LATE (sem saldo). LATE não é final: a cobrança tenta de
    novo a cada dia. PAID é final, e é o que torna a cobrança
    idempotente — parcela paga é ignorada.

    `transaction_id` aponta pra linha do extrato que a quitou.
    """

    __tablename__ = "loan_installment"

    id = Column(Integer, primary_key=True)
    loan_id = Column(Integer, ForeignKey(Loan.id), nullable=False)
    number = Column(Integer, nullable=False)
    due_date = Column(Date, nullable=False)
    amount = Column(BigInteger, nullable=False)
    status = Column(String(20), nullable=False)
    transaction_id = Column(Integer, ForeignKey(Transaction.id), nullable=True)
    paid_at = Column(DateTime, nullable=True)

    __table_args__ = (UniqueConstraint("loan_id", "number"),)

    PENDING = "PENDING"
    PAID = "PAID"
    LATE = "LATE"

    loan = relationship("Loan", foreign_keys=[loan_id], back_populates="installment_list")
    transaction = relationship("Transaction", foreign_keys=[transaction_id])
