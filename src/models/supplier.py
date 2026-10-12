from sqlalchemy import CHAR, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from models.base import Base
from models import Team


class Supplier(Base):
    """Um fornecedor cadastrado pela equipe: o único destino de um pagamento.

    Só entra com CNPJ válido (máscara 00.000.000/0000-00), único por
    equipe. No reembolso ele também aparece: é quem emitiu a nota fiscal
    que o responsável pagou do próprio bolso.
    """

    __tablename__ = "supplier"

    id = Column(Integer, primary_key=True)
    supplier_key = Column(CHAR(36), nullable=False)
    team_id = Column(Integer, ForeignKey(Team.id), nullable=False)
    name = Column(String(255), nullable=False)
    document_number = Column(CHAR(18), nullable=False)
    pix_key = Column(String(77), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("supplier_key"),
        UniqueConstraint("team_id", "document_number"),
    )
