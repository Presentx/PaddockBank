DEFAULT_LIMIT = 10
DEFAULT_PAGE = 0


def read_page(query_params) -> tuple:
    """Lê `limit` e `page` da query string e devolve (limit, page, offset).

    Os `int()` não têm try: quem chama já passou pelo
    @SchemaHandler.validate_query_params, e o schema da listagem garante
    que só chega dígito (limit até 100).
    """
    limit = int(query_params.get("limit", DEFAULT_LIMIT))
    page = int(query_params.get("page", DEFAULT_PAGE))

    return limit, page, page * limit


def split_page(items: list, limit: int) -> tuple:
    """Separa a página do item extra que só serve pra dizer se há próxima.

    Todo `list_page` dos repositories pede UM a mais que o limite: se o
    extra veio, existe próxima página, e ele não entra na resposta.
    """
    if len(items) > limit:
        return items[:limit], False

    return items, True


def build_page_envelope(data: list, limit: int, page: int, is_last_page: bool) -> dict:
    """O envelope de toda listagem: data, limit, page e is_last_page.

    A paginação é assunto do endereço (?limit=&page=), não da entidade:
    por isso quem monta o envelope é o resource, e não o DTO.
    """
    return {
        "data": data,
        "limit": limit,
        "page": page,
        "is_last_page": is_last_page,
    }
