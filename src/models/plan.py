from sqlalchemy import BigInteger, Column, DateTime, Integer, String, UniqueConstraint, func
from models.base import Base


class Plan(Base):
    """A tabela de planos: onde moram os parâmetros comerciais do banco.

    As duas linhas (FREE e PRO) nascem com o banco, nos `INSERT` do
    database/database.sql. Tarifa, juros e mensalidade são lidos daqui a
    cada operação — nenhum desses números está escrito no código.

    Valores em centavos; percentuais em pontos-base (100 bps = 1%).
    """

    __tablename__ = "plan"

    id = Column(Integer, primary_key=True)
    enumerator = Column(String(50), nullable=False)
    outgoing_fee_bps = Column(Integer, nullable=False)
    min_outgoing_fee = Column(BigInteger, nullable=False)
    handover_fee = Column(BigInteger, nullable=False)
    monthly_price = Column(BigInteger, nullable=False)
    loan_monthly_rate_bps = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (UniqueConstraint("enumerator"),)

    FREE = "FREE"
    PRO = "PRO"
