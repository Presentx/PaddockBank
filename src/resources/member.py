from fastapi import Request
from fastapi import status as http_status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from controllers import MemberController
from utils.pagination import build_page_envelope, read_page
from utils.schema_handler import SchemaHandler


class MemberResource:
    """A porta de entrada HTTP dos responsáveis.

    Mesmo desenho do TeamResource, e a explicação completa está lá.
    """

    @SchemaHandler.validate("post_member.json")
    def on_post(self, team_key: str, payload: dict) -> JSONResponse:
        controller = MemberController()
        member = controller.create(team_key, payload)

        return JSONResponse(
            content=jsonable_encoder(member),
            status_code=http_status.HTTP_201_CREATED,
        )

    @SchemaHandler.validate("patch_member.json")
    def on_patch_by_key(self, member_key: str, payload: dict) -> JSONResponse:
        controller = MemberController()
        member = controller.update(member_key, payload)

        return JSONResponse(
            content=jsonable_encoder(member),
            status_code=http_status.HTTP_200_OK,
        )

    def on_get_by_key(self, member_key: str) -> JSONResponse:
        controller = MemberController()
        member = controller.get_by_key(member_key)

        return JSONResponse(
            content=jsonable_encoder(member),
            status_code=http_status.HTTP_200_OK,
        )

    @SchemaHandler.validate_query_params("get_members.json")
    def on_get_list(self, team_key: str, request: Request) -> JSONResponse:
        controller = MemberController()

        limit, page, offset = read_page(request.query_params)
        role_key = request.query_params.get("role_key")

        members_page = controller.get_list(team_key, limit, offset, role_key)

        page_envelope = build_page_envelope(members_page["data"], limit, page, members_page["is_last_page"])

        return JSONResponse(
            content=jsonable_encoder(page_envelope),
            status_code=http_status.HTTP_200_OK,
        )
