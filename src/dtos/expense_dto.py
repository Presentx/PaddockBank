from typing import List

from dtos.member_dto import MemberDTO
from models import Expense


class ExpenseDTO:
    """O JSON do pedido de gasto."""

    @staticmethod
    def obj_to_dict(expense: Expense) -> dict:
        """O pedido INTEIRO, com a história de como ele chegou aqui.

        Cada linha de `expense_status_event` vira um item de
        `status_events`: o status, o instante, quem causou e o
        `request_id` da requisição.
        """
        dto = ExpenseDTO.obj_to_simplified_dict(expense)
        dto["status_events"] = []

        for status_event in expense.status_events:
            status_event_dto = dict()
            status_event_dto["status"] = status_event.status.enumerator
            status_event_dto["event_datetime"] = status_event.event_datetime.isoformat()
            status_event_dto["member_key"] = status_event.member.member_key
            status_event_dto["request_id"] = status_event.request_id

            dto["status_events"].append(status_event_dto)

        return dto

    @staticmethod
    def obj_to_simplified_dict(expense: Expense) -> dict:
        """O pedido sem a trilha — o resumo que a listagem devolve.

        Como no base-service: a trilha mora em outra tabela, e montá-la
        para cada pedido da página custaria uma consulta por pedido.
        """
        dto = dict()
        dto["expense_key"] = expense.expense_key
        dto["status"] = expense.status.enumerator
        dto["kind"] = expense.kind
        dto["amount"] = expense.amount
        dto["description"] = expense.description
        dto["invoice_number"] = expense.invoice_number
        dto["subsystem_key"] = expense.subsystem.subsystem_key
        dto["supplier_key"] = expense.supplier.supplier_key
        dto["requester"] = MemberDTO.obj_to_summary_dict(expense.requester)

        if expense.approver is None:
            dto["approver"] = None
        else:
            dto["approver"] = MemberDTO.obj_to_summary_dict(expense.approver)

        dto["reason"] = expense.reason
        dto["created_at"] = expense.created_at.isoformat()

        return dto

    @staticmethod
    def list_obj_to_list_dict(expenses_list: List[Expense]) -> List[dict]:
        expenses_dict_list = []

        for expense in expenses_list:
            expenses_dict_list.append(ExpenseDTO.obj_to_simplified_dict(expense))

        return expenses_dict_list

    @staticmethod
    def only_obj_key(expense: Expense) -> dict:
        dto = dict()
        dto["expense_key"] = expense.expense_key
        dto["status"] = expense.status.enumerator

        return dto

    @staticmethod
    def paid_to_dict(expense: Expense, fee: int, balance_after: int) -> dict:
        """A resposta da aprovação: o status, a tarifa cobrada e o saldo que sobrou."""
        dto = ExpenseDTO.only_obj_key(expense)
        dto["fee"] = fee
        dto["balance_after"] = balance_after

        return dto
