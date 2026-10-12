from sqlalchemy import Column, DateTime, Integer, String, UniqueConstraint, func
from models.base import Base


class ExpenseStatus(Base):
    """A lista fechada de status de um pedido de gasto.

    PENDING é o único status de onde se sai; PAID, REJECTED e CANCELED
    são finais. Quem decide a transição é o ExpenseController.
    """

    __tablename__ = "expense_status"

    id = Column(Integer, primary_key=True)
    enumerator = Column(String(50), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (UniqueConstraint("enumerator"),)

    PENDING = "PENDING"
    PAID = "PAID"
    REJECTED = "REJECTED"
    CANCELED = "CANCELED"
