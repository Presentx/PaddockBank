from os import environ

from tests.utils.requisition import ClientRequisition


INTERNAL_TOKEN = environ.get("INTERNAL_TOKEN", "default_token")


class RequestGenerator:
    """Uma chamada pronta por rota da API.

    Todo método devolve a dupla (status, corpo). O `member_key` é QUEM
    está agindo: ele viaja no cabeçalho X-Member-Key, como o gateway
    mandaria — nunca no corpo. As três rotas sem sessão (cadastro da
    equipe, depósito e cobrança de parcelas) não o recebem.
    """

    @staticmethod
    def send(method: str, endpoint: str, member_key: str = None, payload: dict = None, params: dict = None, headers: dict = None):
        request_headers = {"INTERNAL-TOKEN": INTERNAL_TOKEN}

        if member_key is not None:
            request_headers["X-Member-Key"] = member_key

        if headers is not None:
            request_headers.update(headers)

        response = ClientRequisition.send(
            method, endpoint, payload=payload, headers=request_headers, query_params=params
        )

        return response.response_status, response.response_json

    # ── sample_entity (o molde do base-service) ─────────────────────
    @staticmethod
    def POST_sample_entity(sample_entity_payload: dict):
        return RequestGenerator.send("POST", "/sample_entity", payload=sample_entity_payload)

    @staticmethod
    def GET_sample_entity(sample_entity_key: str):
        return RequestGenerator.send("GET", f"/sample_entity/{sample_entity_key}")

    @staticmethod
    def PUT_sample_entity(sample_entity_key: str, update_payload: dict):
        return RequestGenerator.send("PUT", f"/sample_entity/{sample_entity_key}", payload=update_payload)

    @staticmethod
    def PUT_webhook_sample_entity(sample_entity_key: str):
        return RequestGenerator.send("PUT", f"/webhook/sample_entity/{sample_entity_key}/increment_counter")

    @staticmethod
    def GET_sample_entities(params: dict = None):
        return RequestGenerator.send("GET", "/sample_entities", params=params)

    # ── Equipe e passagem de gestão ─────────────────────────────────
    @staticmethod
    def POST_team(team_payload: dict):
        return RequestGenerator.send("POST", "/team", payload=team_payload)

    @staticmethod
    def GET_team(team_key: str, member_key: str = None):
        return RequestGenerator.send("GET", f"/team/{team_key}", member_key)

    @staticmethod
    def POST_handover(team_key: str, member_key: str, handover_payload: dict):
        return RequestGenerator.send("POST", f"/team/{team_key}/handover", member_key, handover_payload)

    # ── Cargos ──────────────────────────────────────────────────────
    @staticmethod
    def POST_role(team_key: str, member_key: str, role_payload: dict):
        return RequestGenerator.send("POST", f"/team/{team_key}/role", member_key, role_payload)

    @staticmethod
    def PATCH_role(role_key: str, member_key: str, role_payload: dict):
        return RequestGenerator.send("PATCH", f"/role/{role_key}", member_key, role_payload)

    @staticmethod
    def GET_roles(team_key: str, member_key: str, params: dict = None):
        return RequestGenerator.send("GET", f"/team/{team_key}/roles", member_key, params=params)

    # ── Responsáveis ────────────────────────────────────────────────
    @staticmethod
    def POST_member(team_key: str, member_key: str, member_payload: dict):
        return RequestGenerator.send("POST", f"/team/{team_key}/member", member_key, member_payload)

    @staticmethod
    def PATCH_member(target_member_key: str, member_key: str, member_payload: dict):
        return RequestGenerator.send("PATCH", f"/member/{target_member_key}", member_key, member_payload)

    @staticmethod
    def GET_member(target_member_key: str, member_key: str):
        return RequestGenerator.send("GET", f"/member/{target_member_key}", member_key)

    @staticmethod
    def GET_members(team_key: str, member_key: str, params: dict = None):
        return RequestGenerator.send("GET", f"/team/{team_key}/members", member_key, params=params)

    # ── Fornecedores ────────────────────────────────────────────────
    @staticmethod
    def POST_supplier(team_key: str, member_key: str, supplier_payload: dict):
        return RequestGenerator.send("POST", f"/team/{team_key}/supplier", member_key, supplier_payload)

    @staticmethod
    def GET_suppliers(team_key: str, member_key: str, params: dict = None):
        return RequestGenerator.send("GET", f"/team/{team_key}/suppliers", member_key, params=params)

    # ── Subsistemas ─────────────────────────────────────────────────
    @staticmethod
    def POST_subsystem(team_key: str, member_key: str, subsystem_payload: dict):
        return RequestGenerator.send("POST", f"/team/{team_key}/subsystem", member_key, subsystem_payload)

    @staticmethod
    def PATCH_subsystem(subsystem_key: str, member_key: str, subsystem_payload: dict):
        return RequestGenerator.send("PATCH", f"/subsystem/{subsystem_key}", member_key, subsystem_payload)

    @staticmethod
    def GET_subsystems(team_key: str, member_key: str, params: dict = None):
        return RequestGenerator.send("GET", f"/team/{team_key}/subsystems", member_key, params=params)

    # ── Conta, depósito e extrato ───────────────────────────────────
    @staticmethod
    def GET_account(account_key: str, member_key: str):
        return RequestGenerator.send("GET", f"/account/{account_key}", member_key)

    @staticmethod
    def PATCH_account(account_key: str, member_key: str, account_payload: dict):
        return RequestGenerator.send("PATCH", f"/account/{account_key}", member_key, account_payload)

    @staticmethod
    def POST_deposit(pix_key: str, deposit_payload: dict):
        return RequestGenerator.send("POST", f"/pix/{pix_key}/deposit", payload=deposit_payload)

    @staticmethod
    def GET_statement(account_key: str, member_key: str, params: dict = None):
        return RequestGenerator.send("GET", f"/account/{account_key}/statement", member_key, params=params)

    # ── Pedidos de gasto ────────────────────────────────────────────
    @staticmethod
    def POST_expense(member_key: str, expense_payload: dict, headers: dict = None):
        return RequestGenerator.send("POST", "/expense", member_key, expense_payload, headers=headers)

    @staticmethod
    def GET_expense(expense_key: str, member_key: str):
        return RequestGenerator.send("GET", f"/expense/{expense_key}", member_key)

    @staticmethod
    def GET_expenses(team_key: str, member_key: str, params: dict = None):
        return RequestGenerator.send("GET", f"/team/{team_key}/expenses", member_key, params=params)

    @staticmethod
    def PUT_expense_approve(expense_key: str, member_key: str, headers: dict = None):
        return RequestGenerator.send("PUT", f"/expense/{expense_key}/approve", member_key, headers=headers)

    @staticmethod
    def PUT_expense_reject(expense_key: str, member_key: str, reason: str = "Fora do planejamento da temporada"):
        return RequestGenerator.send("PUT", f"/expense/{expense_key}/reject", member_key, {"reason": reason})

    @staticmethod
    def PUT_expense_cancel(expense_key: str, member_key: str):
        return RequestGenerator.send("PUT", f"/expense/{expense_key}/cancel", member_key)

    # ── Crédito ─────────────────────────────────────────────────────
    @staticmethod
    def POST_loan(account_key: str, member_key: str, loan_payload: dict):
        return RequestGenerator.send("POST", f"/account/{account_key}/loan", member_key, loan_payload)

    @staticmethod
    def GET_loan(loan_key: str, member_key: str):
        return RequestGenerator.send("GET", f"/loan/{loan_key}", member_key)

    @staticmethod
    def POST_charge_due(charge_payload: dict = None):
        return RequestGenerator.send("POST", "/loan-installments/charge-due", payload=charge_payload)
