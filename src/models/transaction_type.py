from sqlalchemy import Column, DateTime, Integer, String, UniqueConstraint, func
from models.base import Base


class TransactionType(Base):
    """A lista fechada de tipos de linha do extrato.

    Repare que a tarifa não é uma coluna do pagamento: ela é uma linha
    própria (FEE, ou HANDOVER_FEE na passagem de gestão). Assim o
    extrato mostra o que saiu pro fornecedor e o que ficou com o banco
    em linhas separadas, cada uma com o seu saldo resultante.
    """

    __tablename__ = "transaction_type"

    id = Column(Integer, primary_key=True)
    enumerator = Column(String(50), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (UniqueConstraint("enumerator"),)

    DEPOSIT = "DEPOSIT"
    SUPPLIER_PAYMENT = "SUPPLIER_PAYMENT"
    REIMBURSEMENT = "REIMBURSEMENT"
    FEE = "FEE"
    HANDOVER_FEE = "HANDOVER_FEE"
    LOAN_DISBURSEMENT = "LOAN_DISBURSEMENT"
    LOAN_INSTALLMENT = "LOAN_INSTALLMENT"
