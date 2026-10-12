from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import func

from database import Context
from models import Account, Loan, LoanInstallment, Member, Transaction


class LoanRepository:
    """As consultas dos créditos e das parcelas."""

    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def create(
        self,
        account: Account,
        requester: Member,
        principal: int,
        monthly_rate_bps: int,
        installments: int,
        installment_amount: int,
        purpose: str,
        idempotency_key: str,
    ) -> Loan:
        loan = Loan()

        loan.loan_key = str(uuid4())
        loan.account_id = account.id
        loan.requester = requester
        loan.status = Loan.ACTIVE
        loan.principal = principal
        loan.monthly_rate_bps = monthly_rate_bps
        loan.installments = installments
        loan.installment_amount = installment_amount
        loan.purpose = purpose
        loan.idempotency_key = idempotency_key

        self.session.add(loan)
        return loan

    def add_installment(self, loan: Loan, number: int, due_date: date, amount: int) -> LoanInstallment:
        installment = LoanInstallment()

        installment.number = number
        installment.due_date = due_date
        installment.amount = amount
        installment.status = LoanInstallment.PENDING

        loan.installment_list.append(installment)
        return installment

    def mark_installment_paid(self, installment: LoanInstallment, transaction: Transaction) -> None:
        installment.status = LoanInstallment.PAID
        installment.transaction = transaction
        installment.paid_at = datetime.now()

    def mark_installment_late(self, installment: LoanInstallment) -> None:
        installment.status = LoanInstallment.LATE

    def update_status(self, loan: Loan, new_status: str) -> None:
        loan.status = new_status

    def get_by_key(self, loan_key: str) -> Loan:
        return self.session.query(Loan).filter(Loan.loan_key == loan_key).first()

    def get_by_idempotency_key(self, account_id: int, idempotency_key: str) -> Loan:
        return (
            self.session.query(Loan)
            .filter(Loan.account_id == account_id, Loan.idempotency_key == idempotency_key)
            .first()
        )

    def list_open_by_account(self, account_id: int) -> list:
        """Os créditos ainda não quitados da conta, do mais novo pro mais antigo."""
        return (
            self.session.query(Loan)
            .filter(Loan.account_id == account_id, Loan.status != Loan.PAID)
            .order_by(Loan.id.desc())
            .all()
        )

    def count_installments(self, loan_id: int, status: str) -> int:
        return (
            self.session.query(func.count(LoanInstallment.id))
            .filter(LoanInstallment.loan_id == loan_id, LoanInstallment.status == status)
            .scalar()
        )

    def count_late_installments_by_account(self, account_id: int) -> int:
        return (
            self.session.query(func.count(LoanInstallment.id))
            .join(LoanInstallment.loan)
            .filter(Loan.account_id == account_id, LoanInstallment.status == LoanInstallment.LATE)
            .scalar()
        )

    def sum_unpaid_installments_by_account(self, account_id: int) -> int:
        """O saldo devedor da conta: a soma das parcelas ainda não pagas.

        `func.sum` devolve None quando não há linha nenhuma, e o
        `coalesce` troca esse None por zero — conta sem crédito deve
        zero, não "nada".
        """
        total = (
            self.session.query(func.coalesce(func.sum(LoanInstallment.amount), 0))
            .join(LoanInstallment.loan)
            .filter(Loan.account_id == account_id, LoanInstallment.status != LoanInstallment.PAID)
            .scalar()
        )

        return int(total)

    def list_due_installment_ids(self, reference_date: date) -> list:
        """Os ids das parcelas vencidas e não pagas, da mais antiga pra mais nova.

        Devolve só os IDS, e não os objetos, de propósito: a cobrança
        processa cada parcela numa transação própria e precisa relê-la
        TRAVADA (`get_installment_for_update`). Um objeto trazido aqui
        estaria velho no instante em que fosse usado.
        """
        rows = (
            self.session.query(LoanInstallment.id)
            .filter(LoanInstallment.due_date <= reference_date, LoanInstallment.status != LoanInstallment.PAID)
            .order_by(LoanInstallment.due_date.asc(), LoanInstallment.id.asc())
            .all()
        )

        installment_ids = []
        for row in rows:
            installment_ids.append(row[0])

        return installment_ids

    def get_installment_for_update(self, installment_id: int) -> LoanInstallment:
        """A parcela, TRAVADA até o fim da transação.

        Duas execuções da cobrança ao mesmo tempo entram em fila aqui: a
        segunda espera o `commit` da primeira e já lê a parcela PAID.
        """
        return (
            self.session.query(LoanInstallment)
            .filter(LoanInstallment.id == installment_id)
            .populate_existing()
            .with_for_update()
            .first()
        )
