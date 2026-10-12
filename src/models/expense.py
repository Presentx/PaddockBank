from sqlalchemy import BigInteger, CHAR, CheckConstraint, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import relationship
from models.base import Base
from models import Account, ExpenseStatus, Member, Subsystem, Supplier


class Expense(Base):
    """Um pedido de gasto: a única forma de o dinheiro sair da conta.

    Dois tipos (`kind`), e o que muda entre eles é quem recebe:

      • SUPPLIER_PAYMENT — a equipe paga o fornecedor;
      • REIMBURSEMENT    — a equipe devolve a um responsável o que ele
                           pagou ao fornecedor do próprio bolso. Exige
                           o número da nota fiscal.

    `requester_member_id` e `approver_member_id` vêm SEMPRE da sessão,
    nunca do corpo: ninguém solicita nem aprova em nome de outro.

    A nota fiscal (`invoice_number`) de um fornecedor só pode estar em
    um pedido PENDING ou PAID por vez — o índice único parcial
    `expense_open_invoice` do database/database.sql cobra isso mesmo sob
    pedidos simultâneos.

    A `idempotency_key` é única por solicitante: repetir o mesmo POST
    devolve o pedido original em vez de reservar o orçamento duas vezes.
    """

    __tablename__ = "expense"

    id = Column(Integer, primary_key=True)
    expense_key = Column(CHAR(36), nullable=False)
    account_id = Column(Integer, ForeignKey(Account.id), nullable=False)
    subsystem_id = Column(Integer, ForeignKey(Subsystem.id), nullable=False)
    supplier_id = Column(Integer, ForeignKey(Supplier.id), nullable=False)
    requester_member_id = Column(Integer, ForeignKey(Member.id), nullable=False)
    approver_member_id = Column(Integer, ForeignKey(Member.id), nullable=True)
    status_id = Column(Integer, ForeignKey(ExpenseStatus.id), nullable=False)
    kind = Column(String(50), nullable=False)
    amount = Column(BigInteger, nullable=False)
    description = Column(String(255), nullable=False)
    invoice_number = Column(String(60), nullable=True)
    idempotency_key = Column(String(64), nullable=False)
    reason = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("expense_key"),
        UniqueConstraint("requester_member_id", "idempotency_key"),
        CheckConstraint("amount > 0"),
    )

    SUPPLIER_PAYMENT = "SUPPLIER_PAYMENT"
    REIMBURSEMENT = "REIMBURSEMENT"

    account = relationship("Account", foreign_keys=[account_id])
    subsystem = relationship("Subsystem", foreign_keys=[subsystem_id], lazy="selectin")
    supplier = relationship("Supplier", foreign_keys=[supplier_id], lazy="selectin")
    requester = relationship("Member", foreign_keys=[requester_member_id], lazy="selectin")
    approver = relationship("Member", foreign_keys=[approver_member_id], lazy="selectin")
    status = relationship("ExpenseStatus", foreign_keys=[status_id], lazy="selectin")

    # No padrão (lazy) de propósito, como no base-service: só o DTO de UM
    # pedido toca na trilha. A listagem usa o resumo, sem ela.
    status_events = relationship(
        "ExpenseStatusEvent",
        back_populates="expense",
        order_by="asc(ExpenseStatusEvent.id)",
    )
