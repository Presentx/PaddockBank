from datetime import datetime
from uuid import uuid4

from database import Context
from models import Account, Expense, ExpenseStatus, ExpenseStatusEvent, Member, Subsystem, Supplier


class ExpenseRepository:
    """As consultas dos pedidos de gasto."""

    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def create(
        self,
        account: Account,
        subsystem: Subsystem,
        supplier: Supplier,
        requester: Member,
        expense_data: dict,
        request_id: str,
    ) -> Expense:
        expense = Expense()

        expense.expense_key = str(uuid4())
        expense.account_id = account.id
        expense.subsystem = subsystem
        expense.supplier = supplier
        expense.requester = requester
        expense.kind = expense_data["kind"]
        expense.amount = expense_data["amount"]
        expense.description = expense_data["description"]
        expense.invoice_number = expense_data.get("invoice_number")
        expense.idempotency_key = expense_data["idempotency_key"]

        # O primeiro evento da trilha é o PENDING do próprio registro:
        # o histórico não começa pela metade.
        self.update_status(expense, ExpenseStatus.PENDING, requester, request_id)

        self.session.add(expense)
        return expense

    def update_status(self, expense: Expense, new_status_enumerator: str, member: Member, request_id: str) -> None:
        """Muda o status do pedido e acrescenta a linha do histórico.

        Nada é salvo aqui: o evento entra na sessão junto com o pedido,
        e os dois vão pro banco no mesmo `commit` do controller.
        """
        new_status = self.get_status(new_status_enumerator)
        expense.status = new_status

        new_status_event = ExpenseStatusEvent()
        new_status_event.status = new_status
        new_status_event.member = member
        new_status_event.request_id = request_id
        new_status_event.event_datetime = datetime.now()

        expense.status_events.append(new_status_event)

    def update_decision(self, expense: Expense, approver: Member, reason: str = None) -> None:
        expense.approver = approver
        expense.reason = reason

    def get_status(self, enumerator: str) -> ExpenseStatus:
        return self.session.query(ExpenseStatus).filter(ExpenseStatus.enumerator == enumerator).one()

    def get_by_key(self, expense_key: str) -> Expense:
        return self.session.query(Expense).filter(Expense.expense_key == expense_key).first()

    def get_by_key_for_update(self, expense_key: str) -> Expense:
        """O pedido, TRAVADO até o fim da transação.

        É a primeira trava de aprovar, recusar e cancelar: duas decisões
        sobre o mesmo pedido entram em fila aqui, e a segunda já lê o
        status que a primeira gravou.
        """
        return (
            self.session.query(Expense)
            .filter(Expense.expense_key == expense_key)
            .populate_existing()
            .with_for_update()
            .first()
        )

    def get_by_idempotency_key(self, requester_member_id: int, idempotency_key: str) -> Expense:
        return (
            self.session.query(Expense)
            .filter(Expense.requester_member_id == requester_member_id, Expense.idempotency_key == idempotency_key)
            .first()
        )

    def get_open_by_invoice(self, supplier_id: int, invoice_number: str) -> Expense:
        """O pedido PENDING ou PAID que já usa esta nota deste fornecedor, se houver."""
        return (
            self.session.query(Expense)
            .join(Expense.status)
            .filter(
                Expense.supplier_id == supplier_id,
                Expense.invoice_number == invoice_number,
                ExpenseStatus.enumerator.in_([ExpenseStatus.PENDING, ExpenseStatus.PAID]),
            )
            .first()
        )

    def list_page(self, account_id: int, limit: int, offset: int, status_enumerators: list = None) -> list:
        query = self.session.query(Expense).filter(Expense.account_id == account_id)

        if status_enumerators:
            query = query.join(Expense.status).filter(ExpenseStatus.enumerator.in_(status_enumerators))

        query = query.order_by(Expense.created_at.desc(), Expense.id.desc())

        return query.limit(limit + 1).offset(offset).all()
