from os import environ
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError


RESET_QUERIES = [
    "DROP SCHEMA public CASCADE;",
    "CREATE SCHEMA public;",
    "GRANT ALL ON SCHEMA public TO CURRENT_USER;",
    "GRANT ALL ON SCHEMA public TO public;",
]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_FILE = PROJECT_ROOT / "database" / "database.sql"

DEFAULT_DATABASE_URL = "postgresql+psycopg2://bootcamp:bootcamp@localhost:5432/bootcamp"

DATABASE_OFFLINE = (
    "Não consegui falar com o banco em {host}:{port}.\n"
    "Ele precisa estar de pé pros testes rodarem. Suba com:  docker compose up\n"
    "Se ele já está de pé, confira a porta na DATABASE_URL do seu .env."
)


class DbUtils:
    """As duas únicas conversas diretas dos testes com o banco.

    O cenário de todo teste nasce PELA API, com `POST`, como um cliente
    faria. Este arquivo existe para as duas coisas que a API não tem
    como oferecer a um teste:

      • `rollback()` — zerar o banco. Quase nenhum teste precisa dele:
        cada um cria a própria equipe e só olha o que é dela. A exceção
        são os testes da cobrança de parcelas
        (tests/integration/loan/test_loan.py): a cobrança varre o banco
        INTEIRO e responde quantas parcelas cobrou, então o teste
        precisa de um banco sem as parcelas dos outros;

      • `expire_grace()` — fazer o tempo passar. A carência de tarifas
        dura 60 dias, e não existe rota (nem deveria existir) que
        encurte a carência de uma conta. Um teste de caixa-preta não
        tem como esperar 60 dias; então ele empurra o `grace_until` da
        conta para ontem, aqui, e a partir daí volta a falar só por
        HTTP.

    A segunda é uma exceção consciente à regra "o teste não monta
    cenário pelo banco" — e é a única. Ela não inventa um estado que a
    API não produziria: produz exatamente o estado em que a conta
    estará no 61º dia.
    """

    @staticmethod
    def database_url() -> str:
        return environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

    @staticmethod
    def rollback() -> None:
        """Apaga o schema `public` inteiro e roda o database/database.sql de novo.

        O nome engana um pouco: isto não desfaz uma transação.
        """
        DbUtils._execute(RESET_QUERIES + [SCHEMA_FILE.read_text(encoding="utf-8")])

    @staticmethod
    def expire_grace(account_key: str) -> None:
        """Encerra a carência da conta: a partir de agora, as tarifas valem."""
        if not all(character in "0123456789abcdef-" for character in account_key):
            raise ValueError(f"account_key fora do formato: {account_key}")

        DbUtils._execute([f"UPDATE account SET grace_until = CURRENT_DATE - 1 WHERE account_key = '{account_key}';"])

    @staticmethod
    def _execute(queries: list) -> None:
        engine = create_engine(DbUtils.database_url(), isolation_level="AUTOCOMMIT")

        try:
            with engine.connect() as connection:
                for query in queries:
                    connection.exec_driver_sql(query)
        except OperationalError:
            message = DATABASE_OFFLINE.format(host=engine.url.host, port=engine.url.port)
            raise RuntimeError(message) from None
        finally:
            engine.dispose()
