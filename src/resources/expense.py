from fastapi import Request
from fastapi import status as http_status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from controllers import ExpenseController
from utils.pagination import build_page_envelope, read_page
from utils.schema_handler import SchemaHandler


class ExpenseResource:
    """A porta de entrada HTTP dos pedidos de gasto.

    Mesmo desenho do TeamResource, com três rotas de transição: aprovar,
    recusar e cancelar. As três respondem 200.

    Repare no que nenhum método daqui recebe: quem solicita, quem
    aprova, quem cancela. O ator sai da sessão, dentro do controller.
    """

    @SchemaHandler.validate("post_expense.json")
    def on_post(self, payload: dict) -> JSONResponse:
        controller = ExpenseController()
        expense, was_created = controller.create(payload)

        if was_created:
            status_code = http_status.HTTP_201_CREATED
        else:
            status_code = http_status.HTTP_200_OK

        return JSONResponse(content=jsonable_encoder(expense), status_code=status_code)

    def on_get_by_key(self, expense_key: str) -> JSONResponse:
        controller = ExpenseController()
        expense = controller.get_by_key(expense_key)

        return JSONResponse(
            content=jsonable_encoder(expense),
            status_code=http_status.HTTP_200_OK,
        )

    @SchemaHandler.validate_query_params("get_expenses.json")
    def on_get_list(self, team_key: str, request: Request) -> JSONResponse:
        controller = ExpenseController()

        limit, page, offset = read_page(request.query_params)
        status_enumerators = request.query_params.getlist("status")

        expenses_page = controller.get_list(team_key, limit, offset, status_enumerators)

        page_envelope = build_page_envelope(expenses_page["data"], limit, page, expenses_page["is_last_page"])

        return JSONResponse(
            content=jsonable_encoder(page_envelope),
            status_code=http_status.HTTP_200_OK,
        )

    def on_put_approve(self, expense_key: str) -> JSONResponse:
        controller = ExpenseController()
        expense = controller.approve(expense_key)

        return JSONResponse(
            content=jsonable_encoder(expense),
            status_code=http_status.HTTP_200_OK,
        )

    @SchemaHandler.validate("put_expense_reject.json")
    def on_put_reject(self, expense_key: str, payload: dict) -> JSONResponse:
        controller = ExpenseController()
        expense = controller.reject(expense_key, payload["reason"])

        return JSONResponse(
            content=jsonable_encoder(expense),
            status_code=http_status.HTTP_200_OK,
        )

    def on_put_cancel(self, expense_key: str) -> JSONResponse:
        controller = ExpenseController()
        expense = controller.cancel(expense_key)

        return JSONResponse(
            content=jsonable_encoder(expense),
            status_code=http_status.HTTP_200_OK,
        )
