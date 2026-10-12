from fastapi import Request
from fastapi import status as http_status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from controllers import RoleController
from utils.pagination import build_page_envelope, read_page
from utils.schema_handler import SchemaHandler


class RoleResource:
    """A porta de entrada HTTP dos cargos.

    Mesmo desenho do TeamResource, e a explicação completa está lá:
    confere o corpo, chama o controller, devolve a resposta.
    """

    @SchemaHandler.validate("post_role.json")
    def on_post(self, team_key: str, payload: dict) -> JSONResponse:
        controller = RoleController()
        role = controller.create(team_key, payload)

        return JSONResponse(
            content=jsonable_encoder(role),
            status_code=http_status.HTTP_201_CREATED,
        )

    @SchemaHandler.validate("patch_role.json")
    def on_patch_by_key(self, role_key: str, payload: dict) -> JSONResponse:
        controller = RoleController()
        role = controller.update(role_key, payload)

        return JSONResponse(
            content=jsonable_encoder(role),
            status_code=http_status.HTTP_200_OK,
        )

    @SchemaHandler.validate_query_params("get_roles.json")
    def on_get_list(self, team_key: str, request: Request) -> JSONResponse:
        controller = RoleController()

        limit, page, offset = read_page(request.query_params)
        roles_page = controller.get_list(team_key, limit, offset)

        page_envelope = build_page_envelope(roles_page["data"], limit, page, roles_page["is_last_page"])

        return JSONResponse(
            content=jsonable_encoder(page_envelope),
            status_code=http_status.HTTP_200_OK,
        )
