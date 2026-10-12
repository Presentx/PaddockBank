from fastapi import FastAPI, Request

from utils.member_identity import MEMBER_KEY_HEADER, set_member_key


def register_member_identity_middleware(application: FastAPI) -> None:
    """Põe no contexto QUEM está agindo nesta requisição.

    ────────────────────────────────────────────────────────────────
    DE ONDE VEM A IDENTIDADE
    ────────────────────────────────────────────────────────────────
    Esta API não autentica o usuário final — isso é trabalho do gateway,
    a única porta pública. O gateway confere quem é a pessoa e repassa a
    `member_key` dela no cabeçalho X-Member-Key, junto com o
    INTERNAL-TOKEN.

    É o INTERNAL-TOKEN que torna o cabeçalho confiável: só quem está na
    rede interna o conhece. Por isso este middleware fica por DENTRO do
    internal_token no src/app.py — requisição sem o token leva 403 na
    camada de cima e nunca chega a ter identidade.

    ────────────────────────────────────────────────────────────────
    POR QUE NO CABEÇALHO, E NUNCA NO CORPO
    ────────────────────────────────────────────────────────────────
    Se o corpo dissesse "quem solicita" ou "quem aprova", qualquer
    responsável escreveria ali a chave do financeiro e aprovaria o
    próprio gasto. O ator de toda operação sai daqui, e nenhum schema de
    src/schemas/ aceita um campo com esse papel.

    ────────────────────────────────────────────────────────────────
    O QUE ESTE MIDDLEWARE NÃO FAZ
    ────────────────────────────────────────────────────────────────
    Ele não consulta o banco e não recusa ninguém. Middleware não
    conhece rota, e três rotas daqui não têm sessão (o cadastro da
    equipe, o depósito e a cobrança de parcelas). Quem decide se a
    identidade era obrigatória, se o responsável existe, se está ativo e
    se ocupa o cargo exigido é o controller — veja o `_get_actor` e o
    `_require_finance` do BaseController.
    """

    @application.middleware("http")
    async def identify_member(request: Request, call_next):
        set_member_key(request.headers.get(MEMBER_KEY_HEADER))

        return await call_next(request)
