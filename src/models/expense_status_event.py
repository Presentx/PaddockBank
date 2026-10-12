from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from models.base import Base
from models import Expense, ExpenseStatus, Member


class ExpenseStatusEvent(Base):
    """Uma linha por mudança de status do pedido: o histórico dele.

    Além do status e do instante (como no base-service), cada linha
    guarda QUEM causou a transição e o `request_id` — o X-Request-ID da
    requisição. Com ele dá pra sair de uma linha do histórico e achar,
    no log, a requisição exata que a gerou.

    Ninguém apaga nem altera uma linha daqui.
    """

    __tablename__ = "expense_status_event"

    id = Column(Integer, primary_key=True)
    expense_id = Column(Integer, ForeignKey(Expense.id), nullable=False)
    status_id = Column(Integer, ForeignKey(ExpenseStatus.id), nullable=False)
    member_id = Column(Integer, ForeignKey(Member.id), nullable=False)
    request_id = Column(String(64), nullable=False)
    event_datetime = Column(DateTime, nullable=False)

    expense = relationship("Expense", foreign_keys=[expense_id], back_populates="status_events")
    status = relationship("ExpenseStatus", foreign_keys=[status_id], lazy="selectin")
    member = relationship("Member", foreign_keys=[member_id], lazy="selectin")
