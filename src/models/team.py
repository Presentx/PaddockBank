from sqlalchemy import CHAR, Column, DateTime, Integer, String, UniqueConstraint, func
from models.base import Base


class Team(Base):
    """A equipe: o cliente do banco.

    Ela é identificada pela `team_key`, e não por CNPJ — a maioria das
    equipes de Formula SAE não tem um. O que impede o cadastro repetido
    é o par (nome, universidade).
    """

    __tablename__ = "team"

    id = Column(Integer, primary_key=True)
    team_key = Column(CHAR(36), nullable=False)
    name = Column(String(255), nullable=False)
    university = Column(String(255), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("team_key"),
        UniqueConstraint("name", "university"),
    )
