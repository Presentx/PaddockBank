import os


SERVICE_ROOT = os.path.abspath(os.path.dirname(__file__))

# Onde moram os arquivos de schema — os .json que descrevem o formato
# que cada requisicao precisa ter. Quem le essa pasta e o
# src/utils/schema_handler.py.
SCHEMA_PATH = os.path.join(SERVICE_ROOT, "schemas")

APP_ENV = os.environ.get("APP_ENV", "local")
SERVICE_NAME = os.environ.get("SERVICE_NAME", "paddock-bank-api")

DATABASE_URL = os.environ.get("DATABASE_URL")
INTERNAL_TOKEN = os.environ.get("INTERNAL_TOKEN")

# ─────────────────────────────────────────────────────────────
# Regras do Paddock Bank que NAO dependem do plano
#
# O que muda de um plano pro outro (tarifa, juros, mensalidade) mora na
# tabela `plan`, no banco. O que vale igual pra todo mundo mora aqui.
# ─────────────────────────────────────────────────────────────

# Carencia: nos primeiros dias da conta, nenhuma tarifa e cobrada.
GRACE_PERIOD_DAYS = 60

# Limite de credito: este percentual do saldo medio diario da janela
# abaixo, menos o saldo devedor. O saldo MEDIO mede o dinheiro que
# permanece na conta, e nao o que so passa por ela.
CREDIT_LIMIT_PERCENT = 50
CREDIT_WINDOW_DAYS = 90

# O nome do cargo financeiro quando o cadastro da equipe nao escolhe um.
DEFAULT_FINANCE_ROLE_NAME = "Financeiro"

# Rotas públicas: não exigem o header INTERNAL-TOKEN. São as duas que
# precisam responder pra quem ainda não tem token nenhum: a raiz, que
# diz quem é este serviço, e o health check, que o Docker consulta pra
# saber se a API já está de pé.
BYPASS_ENDPOINTS = [
    "/",
    "/health_check",
]

REQUIRED_VARIABLES = ["DATABASE_URL", "INTERNAL_TOKEN"]


def check_variables():
    missing = []
    for name in REQUIRED_VARIABLES:
        if not globals().get(name):
            missing.append(name)

    if missing:
        raise EnvironmentError(
            f"Faltam variáveis de ambiente: {', '.join(missing)}. "
            "Rodando com 'docker compose up' elas já vêm preenchidas. "
            "Fora do Docker, copie o .env.example para .env."
        )
