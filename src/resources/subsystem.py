from fastapi import Request
from fastapi import status as http_status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from controllers import SubsystemController
from utils.pagination import build_page_envelope, read_page
from utils.schema_handler import SchemaHandler


class SubsystemResource:
    """A porta de entrada HTTP dos subsistemas.

    Mesmo desenho do TeamResource, e a explicação completa está lá.
    """

    @SchemaHandler.validate("post_subsystem.json")
    def on_post(self, team_key: str, payload: dict) -> JSONResponse:
        controller = SubsystemController()
        subsystem = controller.create(team_key, payload)

        return JSONResponse(
            content=jsonable_encoder(subsystem),
            status_code=http_status.HTTP_201_CREATED,
        )

    @SchemaHandler.validate("patch_subsystem.json")
    def on_patch_by_key(self, subsystem_key: str, payload: dict) -> JSONResponse:
        controller = SubsystemController()
        subsystem = controller.update(subsystem_key, payload)

        return JSONResponse(
            content=jsonable_encoder(subsystem),
            status_code=http_status.HTTP_200_OK,
        )

    @SchemaHandler.validate_query_params("get_subsystems.json")
    def on_get_list(self, team_key: str, request: Request) -> JSONResponse:
        controller = SubsystemController()

        limit, page, offset = read_page(request.query_params)
        subsystems_page = controller.get_list(team_key, limit, offset)

        page_envelope = build_page_envelope(subsystems_page["data"], limit, page, subsystems_page["is_last_page"])

        return JSONResponse(
            content=jsonable_encoder(page_envelope),
            status_code=http_status.HTTP_200_OK,
        )
