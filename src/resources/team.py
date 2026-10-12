from fastapi import status as http_status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from controllers import HandoverController, TeamController
from utils.schema_handler import SchemaHandler


class TeamResource:
    """A porta de entrada HTTP da equipe.

    ────────────────────────────────────────────────────────────────
    O QUE UM RESOURCE FAZ — E O QUE ELE NÃO FAZ
    ────────────────────────────────────────────────────────────────
    Ele faz três coisas, nesta ordem, e nada além disso:

      1. confere o corpo da requisição (o decorator do schema);
      2. chama o controller;
      3. devolve o que o controller respondeu.

    Repare no que NÃO está aqui: nenhuma regra de negócio, nenhum `if`
    sobre saldo ou cargo, nenhuma linha de SQL — e nenhuma menção a
    QUEM está chamando. A identidade do responsável (X-Member-Key) não
    passa pelo resource: o middleware a deixa no contexto, e é o
    controller que a lê. Um resource que recebesse a identidade poderia
    repassar a errada.

    Todos os resources do projeto seguem este desenho, e é por isso que
    só este arquivo conta a história.

    ────────────────────────────────────────────────────────────────
    UMA REGRA QUE O CÓDIGO NÃO CONSEGUE COBRAR SOZINHO
    ────────────────────────────────────────────────────────────────
    O `src/app.py` cria UM resource e ele vive enquanto a API estiver no
    ar. Não existe `__init__` aqui, e nenhum método escreve
    `self.alguma_coisa`: o que fosse guardado no `self` seria
    compartilhado por TODAS as requisições ao mesmo tempo.

    ────────────────────────────────────────────────────────────────
    O STATUS DA RESPOSTA É DECIDIDO AQUI
    ────────────────────────────────────────────────────────────────
    201 pra criação, 200 pro resto — e, nas rotas idempotentes, 200
    quando o pedido era uma repetição. Os erros não saem daqui: erro já
    carrega o próprio status (veja src/errors/custom_errors.py), e quem
    o levanta é o controller.
    """

    @SchemaHandler.validate("post_team.json")
    def on_post(self, payload: dict) -> JSONResponse:
        controller = TeamController()
        team = controller.create(payload)

        return JSONResponse(
            content=jsonable_encoder(team),
            status_code=http_status.HTTP_201_CREATED,
        )

    def on_get_by_key(self, team_key: str) -> JSONResponse:
        controller = TeamController()
        team = controller.get_by_key(team_key)

        return JSONResponse(
            content=jsonable_encoder(team),
            status_code=http_status.HTTP_200_OK,
        )

    @SchemaHandler.validate("post_handover.json")
    def on_post_handover(self, team_key: str, payload: dict) -> JSONResponse:
        # 200 nas duas vezes, a primeira e a repetição: a passagem de
        # gestão não cria um recurso que o cliente vá buscar depois —
        # ela muda quem ocupa um cargo que já existia.
        controller = HandoverController()
        handover = controller.create(team_key, payload)

        return JSONResponse(
            content=jsonable_encoder(handover),
            status_code=http_status.HTTP_200_OK,
        )
