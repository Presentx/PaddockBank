from fastapi import status as http_status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from controllers import LoanController
from utils.schema_handler import SchemaHandler


class LoanResource:
    """A porta de entrada HTTP do crédito.

    Mesmo desenho do TeamResource, e a explicação completa está lá.
    """

    @SchemaHandler.validate("post_loan.json")
    def on_post(self, account_key: str, payload: dict) -> JSONResponse:
        controller = LoanController()
        loan, was_created = controller.create(account_key, payload)

        if was_created:
            status_code = http_status.HTTP_201_CREATED
        else:
            status_code = http_status.HTTP_200_OK

        return JSONResponse(content=jsonable_encoder(loan), status_code=status_code)

    def on_get_by_key(self, loan_key: str) -> JSONResponse:
        controller = LoanController()
        loan = controller.get_by_key(loan_key)

        return JSONResponse(
            content=jsonable_encoder(loan),
            status_code=http_status.HTTP_200_OK,
        )

    @SchemaHandler.validate("post_charge_due.json")
    def on_post_charge_due(self, payload: dict = None) -> JSONResponse:
        # O corpo é OPCIONAL (o `= None`): o agendador chama sem corpo
        # nenhum, e a cobrança usa a data de hoje. O schema desta rota
        # aceita o corpo ausente justamente por isso.
        controller = LoanController()
        charge_summary = controller.charge_due(payload)

        return JSONResponse(
            content=jsonable_encoder(charge_summary),
            status_code=http_status.HTTP_200_OK,
        )
