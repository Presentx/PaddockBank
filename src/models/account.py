from sqlalchemy import BigInteger, CHAR, CheckConstraint, Column, Date, DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import relationship
from models.base import Base
from models import Plan, Team


class Account(Base):
    """A conta da equipe — uma por equipe.

    ────────────────────────────────────────────────────────────────
    O SALDO MORA NUMA COLUNA, E O EXTRATO O RECONSTRÓI
    ────────────────────────────────────────────────────────────────
    `balance` é a verdade do agora, em centavos. Cada mudança nele
    acontece junto com uma linha em `transaction`, na mesma transação e
    com a conta travada (veja BaseController._register_movement). Por
    isso a soma do extrato é sempre o saldo.

    ────────────────────────────────────────────────────────────────
    `overdraft`: O NEGATIVO AUTORIZADO
    ────────────────────────────────────────────────────────────────
    O saldo só pode ficar negativo por um motivo: a tarifa de passagem
    de gestão, cobrada mesmo sem saldo. Quando isso acontece, o valor
    descoberto é gravado em `overdraft`, e o CHECK do banco
    (balance >= -overdraft) passa a aceitar exatamente aquele negativo —
    e nada além dele. As entradas seguintes cobrem o descoberto e
    reduzem o `overdraft` de volta a zero.

    O titular da conta não é uma coluna daqui: é o responsável que ocupa
    o cargo financeiro da equipe (veja o Role).
    """

    __tablename__ = "account"

    id = Column(Integer, primary_key=True)
    account_key = Column(CHAR(36), nullable=False)
    team_id = Column(Integer, ForeignKey(Team.id), nullable=False)
    plan_id = Column(Integer, ForeignKey(Plan.id), nullable=False)
    pix_key = Column(CHAR(36), nullable=False)
    balance = Column(BigInteger, nullable=False, default=0)
    overdraft = Column(BigInteger, nullable=False, default=0)
    grace_until = Column(Date, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("account_key"),
        UniqueConstraint("team_id"),
        UniqueConstraint("pix_key"),
        CheckConstraint("overdraft >= 0"),
        CheckConstraint("balance >= -overdraft"),
    )

    team = relationship("Team", foreign_keys=[team_id], lazy="selectin")
    plan = relationship("Plan", foreign_keys=[plan_id], lazy="selectin")
