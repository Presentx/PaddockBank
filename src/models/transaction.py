from sqlalchemy import BigInteger, CHAR, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import relationship
from models.base import Base
from models import Account, Expense, Loan, Subsystem, TransactionType


class Transaction(Base):
    """Uma linha do extrato. Append-only: nunca é alterada nem apagada.

    Uma tabela só para todos os tipos de movimento, com o tipo numa
    coluna: o extrato vira UMA consulta, e a tarifa é só mais uma linha.
    O preço são as colunas que só valem para alguns tipos
    (`expense_id`, `loan_id`, `subsystem_id`), que ficam nuláveis.

    `amount` tem sinal: crédito positivo, débito negativo.
    `balance_after` é o saldo da conta logo depois desta linha.

    A `idempotency_key` só é preenchida no depósito, que é o único
    movimento que nasce direto como linha do extrato. Pedido, crédito e
    passagem de gestão guardam a chave na própria tabela.
    """

    __tablename__ = "transaction"

    id = Column(Integer, primary_key=True)
    transaction_key = Column(CHAR(36), nullable=False)
    account_id = Column(Integer, ForeignKey(Account.id), nullable=False)
    type_id = Column(Integer, ForeignKey(TransactionType.id), nullable=False)
    expense_id = Column(Integer, ForeignKey(Expense.id), nullable=True)
    loan_id = Column(Integer, ForeignKey(Loan.id), nullable=True)
    subsystem_id = Column(Integer, ForeignKey(Subsystem.id), nullable=True)
    amount = Column(BigInteger, nullable=False)
    balance_after = Column(BigInteger, nullable=False)
    counterparty_name = Column(String(255), nullable=True)
    counterparty_document = Column(String(18), nullable=True)
    description = Column(String(255), nullable=True)
    idempotency_key = Column(String(64), nullable=True)
    request_id = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("transaction_key"),
        UniqueConstraint("account_id", "idempotency_key"),
    )

    type = relationship("TransactionType", foreign_keys=[type_id], lazy="selectin")
    subsystem = relationship("Subsystem", foreign_keys=[subsystem_id], lazy="selectin")
    expense = relationship("Expense", foreign_keys=[expense_id])
    loan = relationship("Loan", foreign_keys=[loan_id])
