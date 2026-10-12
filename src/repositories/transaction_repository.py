from datetime import datetime
from uuid import uuid4

from database import Context
from models import Account, Expense, Loan, Subsystem, Transaction, TransactionType


class TransactionRepository:
    """As consultas do extrato.

    Não existe `update` nem `delete` aqui, e não é esquecimento: o
    extrato é append-only. Uma linha errada se corrige com outra linha.
    """

    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def create(
        self,
        account: Account,
        type_enumerator: str,
        amount: int,
        balance_after: int,
        request_id: str,
        counterparty_name: str = None,
        counterparty_document: str = None,
        description: str = None,
        idempotency_key: str = None,
        expense: Expense = None,
        loan: Loan = None,
        subsystem: Subsystem = None,
    ) -> Transaction:
        transaction = Transaction()

        transaction.transaction_key = str(uuid4())
        transaction.account_id = account.id
        transaction.type = self.get_type(type_enumerator)
        transaction.amount = amount
        transaction.balance_after = balance_after
        transaction.request_id = request_id
        transaction.counterparty_name = counterparty_name
        transaction.counterparty_document = counterparty_document
        transaction.description = description
        transaction.idempotency_key = idempotency_key
        transaction.expense = expense
        transaction.loan = loan
        transaction.subsystem = subsystem

        self.session.add(transaction)
        return transaction

    def get_type(self, enumerator: str) -> TransactionType:
        return self.session.query(TransactionType).filter(TransactionType.enumerator == enumerator).one()

    def get_by_idempotency_key(self, account_id: int, idempotency_key: str) -> Transaction:
        return (
            self.session.query(Transaction)
            .filter(Transaction.account_id == account_id, Transaction.idempotency_key == idempotency_key)
            .first()
        )

    def get_by_loan_and_type(self, loan_id: int, type_enumerator: str) -> Transaction:
        """A linha de um tipo ligada a um crédito — a liberação dele, por exemplo."""
        return (
            self.session.query(Transaction)
            .join(Transaction.type)
            .filter(Transaction.loan_id == loan_id, TransactionType.enumerator == type_enumerator)
            .order_by(Transaction.id.asc())
            .first()
        )

    def get_last_before(self, account_id: int, moment: datetime) -> Transaction:
        """A última linha do extrato antes de um instante — ou None.

        O `balance_after` dela é o saldo com que a conta ENTROU naquele
        instante: é o ponto de partida da conta do saldo médio diário.
        """
        return (
            self.session.query(Transaction)
            .filter(Transaction.account_id == account_id, Transaction.created_at < moment)
            .order_by(Transaction.id.desc())
            .first()
        )

    def list_since(self, account_id: int, moment: datetime) -> list:
        """As linhas do extrato de um instante em diante, da mais antiga pra mais nova."""
        return (
            self.session.query(Transaction)
            .filter(Transaction.account_id == account_id, Transaction.created_at >= moment)
            .order_by(Transaction.id.asc())
            .all()
        )

    def list_page(self, account_id: int, limit: int, offset: int, subsystem: Subsystem = None) -> list:
        """A página do extrato, da linha mais nova para a mais antiga.

        A ordem é pelo `id`, e não pelo `created_at`: o pagamento e a
        tarifa dele nascem na mesma transação, com o mesmo instante, e
        só o `id` diz qual veio primeiro.
        """
        query = self.session.query(Transaction).filter(Transaction.account_id == account_id)

        if subsystem is not None:
            query = query.filter(Transaction.subsystem_id == subsystem.id)

        query = query.order_by(Transaction.id.desc())

        return query.limit(limit + 1).offset(offset).all()
