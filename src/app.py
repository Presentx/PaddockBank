from fastapi import FastAPI

from constants import check_variables
from errors import register_error_handlers
from errors.base_error import error_verification
from middlewares import (
    register_internal_token_middleware,
    register_member_identity_middleware,
    register_request_context_middleware,
    register_request_logger_middleware,
    register_session_manager_middleware,
)
from resources import (
    AccountResource,
    ExpenseResource,
    HealthCheckResource,
    LoanResource,
    MemberResource,
    RoleResource,
    SampleEntityResource,
    SubsystemResource,
    SupplierResource,
    TeamResource,
)
from utils.logger import setup_logging


def create_app() -> FastAPI:
    """Monta a aplicação, peça por peça.

    Os três blocos abaixo seguem a ordem em que a requisição encontra
    cada um — de fora pra dentro:
      1. os middlewares    — o que acontece com TODA requisição
      2. as rotas          — o que a API sabe responder
      3. os error handlers — como cada erro vira uma resposta

    Essa ordem serve pra leitura, não é exigência: o FastAPI monta a
    pilha de middlewares na primeira requisição que chega, então
    registrar rota antes ou depois de middleware dá no mesmo. Só a
    ordem DENTRO do bloco de middlewares tem consequência, e ela está
    explicada logo abaixo.
    """
    # Os três None desligam a documentação automática: o FastAPI sabe
    # gerar sozinho umas páginas descrevendo a API, e aqui elas não
    # existem. Pra ver o que cada rota responde, mande uma requisição —
    # tem exemplo pronto de cada uma no README.
    application = FastAPI(
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    # ────────────────────────────────────────────────────────────────
    # Os middlewares — e a ordem deles, que é regra e não gosto
    # ────────────────────────────────────────────────────────────────
    # Middleware é uma camada por fora da aplicação: toda requisição
    # atravessa todas elas na ida, e todas de novo na volta. São como
    # cascas de cebola, e o ÚLTIMO registrado é a casca de FORA.
    #
    # Ou seja: destas quatro linhas, a de BAIXO é a primeira que a
    # requisição encontra, e a de CIMA é a última. Lendo de fora para
    # dentro, acontece isto:
    #
    #     requisição chega
    #           ↓
    #     request_context   dá um identificador único a esta requisição
    #           ↓
    #     request_logger    escreve "ENTROU" e, na volta, "SAIU"
    #           ↓
    #     internal_token    confere o INTERNAL-TOKEN. Sem ele, para aqui
    #           ↓
    #     member_identity   guarda QUEM está agindo (X-Member-Key), pro
    #           ↓           controller conferir. Não recusa ninguém
    #           ↓
    #     session_manager  cuida da sessão de banco: desfaz se deu
    #           ↓           errado, fecha sempre — e nunca salva
    #           ↓
    #     as rotas
    #
    # Cada posição tem um porquê, e trocar duas linhas muda o que a API
    # faz:
    #
    # • O identificador vem ANTES do log: se viesse depois, as linhas de
    #   log da requisição sairiam sem o nome dela, e o middleware
    #   existiria para nada.
    # • O log vem ANTES do token: assim a tentativa recusada com 403
    #   também aparece no log — e essa é justamente a que você quer ver,
    #   porque mil delas seguidas é alguém tentando adivinhar o token.
    # • A identidade fica por DENTRO do token: o X-Member-Key só é
    #   confiável porque veio junto com o INTERNAL-TOKEN, que só o
    #   gateway conhece. Quem não passou pelo token leva 403 na camada
    #   de cima e nunca chega a ter identidade nenhuma.
    # • A sessão de banco fica por DENTRO do token, encostada nas
    #   rotas: quem não passou na porta leva 403 na camada de cima e não
    #   chega a ter uma sessão. É o mais interno de propósito — banco é
    #   o recurso mais caro desta lista, e o último que se empresta.
    #
    # Nada disso é teoria, e dá pra ver com os olhos. Troque as duas
    # últimas linhas de lugar (o identificador passa a ser registrado
    # antes do log, ou seja, a executar DEPOIS dele), chame qualquer
    # rota e olhe o log:
    #
    #     docker compose logs api | grep request_logger | tail -2
    #
    # (O grep é necessário: sem ele o tail pega a linha de acesso do
    # uvicorn, que é outra coisa e não passa por este middleware.)
    #
    # As duas linhas saem com [-] no lugar do identificador: o log
    # aconteceu antes de existir um nome para aquela requisição. Desfaça
    # a troca e o nome volta.
    #
    # Repare no que essa experiência tem de incômodo: a suíte continua
    # TODA VERDE com a ordem trocada. Nenhum teste aqui guarda esta
    # ordem — o preço aparece no dia do incidente, quando o log não
    # servir pra achar a requisição. Teste que não existe não avisa
    # nada, e é por isso que este comentário existe.
    #
    # ATENÇÃO, e é aqui que quase todo mundo tropeça: as cinco linhas
    # abaixo são o DIAGRAMA ACIMA DE TRÁS PRA FRENTE. O FastAPI embrulha
    # a aplicação de dentro pra fora, então o ÚLTIMO registrado é o
    # PRIMEIRO a executar. Leia de baixo pra cima e o diagrama volta.
    register_session_manager_middleware(application)
    register_member_identity_middleware(application)
    register_internal_token_middleware(application)
    register_request_logger_middleware(application)
    register_request_context_middleware(application)

    # ────────────────────────────────────────────────────────────────
    # As rotas — o endereço, o verbo, e quem atende
    # ────────────────────────────────────────────────────────────────
    # Cada linha liga um endereço a um método de um resource. É a lista
    # COMPLETA do que esta API atende: rota que não está aqui não
    # existe, e não há um segundo lugar para procurar.
    #
    # Nos serviços da QI o framework é o Falcon, que descobre o método
    # pelo nome — chegou um POST, ele procura um `on_post`, e o registro
    # é uma linha por ENDEREÇO. O FastAPI não faz essa descoberta, então
    # aqui é uma linha por endereço E verbo. Custa mais linhas; em troca,
    # não existe rota que atenda sem estar escrita nesta lista.
    #
    # Repare no que NÃO está escrito aqui: o status de cada resposta.
    # 200, 201, 204 — todos saem de dentro do resource, que é quem sabe
    # se a coisa foi criada ou concluída. Esta lista diz QUEM
    # atende cada endereço, e mais nada.
    #
    # A convenção dos nomes é a do base-service: um item é SINGULAR
    # (/expense/{key}), a coleção é PLURAL (/team/{key}/expenses). Quem
    # nasce DENTRO de uma equipe é criado no endereço dela
    # (/team/{key}/member) e depois tem endereço próprio (/member/{key}).
    # A ação sobre um item é um pedaço a mais no endereço dele
    # (/expense/{key}/approve).
    health_check_resource = HealthCheckResource()
    sample_entity_resource = SampleEntityResource()
    team_resource = TeamResource()
    role_resource = RoleResource()
    member_resource = MemberResource()
    supplier_resource = SupplierResource()
    subsystem_resource = SubsystemResource()
    account_resource = AccountResource()
    expense_resource = ExpenseResource()
    loan_resource = LoanResource()

    application.add_api_route("/", health_check_resource.on_get_home, methods=["GET"])
    application.add_api_route(
        "/health_check",
        health_check_resource.on_get_health_check,
        methods=["GET"]
    )

    # sample_entity — o molde do base-service
    application.add_api_route("/sample_entity", sample_entity_resource.on_post, methods=["POST"])
    application.add_api_route(
        "/sample_entity/{sample_entity_key}", sample_entity_resource.on_get_by_key, methods=["GET"]
    )
    application.add_api_route(
        "/sample_entity/{sample_entity_key}", sample_entity_resource.on_put_by_key, methods=["PUT"]
    )
    application.add_api_route(
        "/webhook/sample_entity/{sample_entity_key}/increment_counter",
        sample_entity_resource.on_put_increment_counter,
        methods=["PUT"],
    )
    application.add_api_route("/sample_entities", sample_entity_resource.on_get_list, methods=["GET"])

    # Equipe e passagem de gestão
    application.add_api_route("/team", team_resource.on_post, methods=["POST"])
    application.add_api_route("/team/{team_key}", team_resource.on_get_by_key, methods=["GET"])
    application.add_api_route("/team/{team_key}/handover", team_resource.on_post_handover, methods=["POST"])

    # Cargos
    application.add_api_route("/team/{team_key}/role", role_resource.on_post, methods=["POST"])
    application.add_api_route("/role/{role_key}", role_resource.on_patch_by_key, methods=["PATCH"])
    application.add_api_route("/team/{team_key}/roles", role_resource.on_get_list, methods=["GET"])

    # Responsáveis
    application.add_api_route("/team/{team_key}/member", member_resource.on_post, methods=["POST"])
    application.add_api_route("/member/{member_key}", member_resource.on_patch_by_key, methods=["PATCH"])
    application.add_api_route("/member/{member_key}", member_resource.on_get_by_key, methods=["GET"])
    application.add_api_route("/team/{team_key}/members", member_resource.on_get_list, methods=["GET"])

    # Fornecedores
    application.add_api_route("/team/{team_key}/supplier", supplier_resource.on_post, methods=["POST"])
    application.add_api_route("/team/{team_key}/suppliers", supplier_resource.on_get_list, methods=["GET"])

    # Subsistemas
    application.add_api_route("/team/{team_key}/subsystem", subsystem_resource.on_post, methods=["POST"])
    application.add_api_route("/subsystem/{subsystem_key}", subsystem_resource.on_patch_by_key, methods=["PATCH"])
    application.add_api_route("/team/{team_key}/subsystems", subsystem_resource.on_get_list, methods=["GET"])

    # Conta, depósito e extrato
    application.add_api_route("/account/{account_key}", account_resource.on_get_by_key, methods=["GET"])
    application.add_api_route("/account/{account_key}", account_resource.on_patch_by_key, methods=["PATCH"])
    application.add_api_route("/pix/{pix_key}/deposit", account_resource.on_post_deposit, methods=["POST"])
    application.add_api_route("/account/{account_key}/statement", account_resource.on_get_statement, methods=["GET"])

    # Pedidos de gasto
    application.add_api_route("/expense", expense_resource.on_post, methods=["POST"])
    application.add_api_route("/expense/{expense_key}", expense_resource.on_get_by_key, methods=["GET"])
    application.add_api_route("/team/{team_key}/expenses", expense_resource.on_get_list, methods=["GET"])
    application.add_api_route("/expense/{expense_key}/approve", expense_resource.on_put_approve, methods=["PUT"])
    application.add_api_route("/expense/{expense_key}/reject", expense_resource.on_put_reject, methods=["PUT"])
    application.add_api_route("/expense/{expense_key}/cancel", expense_resource.on_put_cancel, methods=["PUT"])

    # Crédito
    application.add_api_route("/account/{account_key}/loan", loan_resource.on_post, methods=["POST"])
    application.add_api_route("/loan/{loan_key}", loan_resource.on_get_by_key, methods=["GET"])
    application.add_api_route("/loan-installments/charge-due", loan_resource.on_post_charge_due, methods=["POST"])

    register_error_handlers(application)

    return application


def main() -> FastAPI:
    # Não deixa a API subir com configuração faltando: é melhor falhar
    # agora, na hora de ligar, do que na cara do cliente mais tarde.
    check_variables()
    error_verification()
    setup_logging()

    return create_app()


app = main()
