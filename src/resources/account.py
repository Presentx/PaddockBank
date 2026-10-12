from fastapi import Request
from fastapi import status as http_status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from controllers import AccountController
from utils.pagination import build_page_envelope, read_page
from utils.schema_handler import SchemaHandler


class AccountResource:
    """A porta de entrada HTTP da conta: consulta, plano, depósito e extrato.

    Mesmo desenho do TeamResource, e a explicação completa está lá.
    """

    def on_get_by_key(self, account_key: str) -> JSONResponse:
        controller = AccountController()
        account = controller.get_by_key(account_key)

        return JSONResponse(
            content=jsonable_encoder(account),
            status_code=http_status.HTTP_200_OK,
        )

    @SchemaHandler.validate("patch_account.json")
    def on_patch_by_key(self, account_key: str, payload: dict) -> JSONResponse:
        controller = AccountController()
        account = controller.update_plan(account_key, payload["plan"])

        return JSONResponse(
            content=jsonable_encoder(account),
            status_code=http_status.HTTP_200_OK,
        )

    @SchemaHandler.validate("post_deposit.json")
    def on_post_deposit(self, pix_key: str, payload: dict) -> JSONResponse:
        controller = AccountController()
        receipt, was_created = controller.deposit(pix_key, payload)

        # O controller diz SE o depósito nasceu agora; o número do HTTP
        # é vocabulário daqui. 201 pro crédito novo, 200 pra repetição
        # da mesma idempotency_key — com o mesmo corpo nos dois casos.
        if was_created:
            status_code = http_status.HTTP_201_CREATED
        else:
            status_code = http_status.HTTP_200_OK

        return JSONResponse(content=jsonable_encoder(receipt), status_code=status_code)

    @SchemaHandler.validate_query_params("get_statement.json")
    def on_get_statement(self, account_key: str, request: Request) -> JSONResponse:
        controller = AccountController()

        limit, page, offset = read_page(request.query_params)
        subsystem_key = request.query_params.get("subsystem_key")

        statement_page = controller.get_statement(account_key, limit, offset, subsystem_key)

        page_envelope = build_page_envelope(statement_page["data"], limit, page, statement_page["is_last_page"])

        return JSONResponse(
            content=jsonable_encoder(page_envelope),
            status_code=http_status.HTTP_200_OK,
        )
