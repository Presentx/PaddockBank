import calendar
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from controllers.base_controller import BaseController
from dtos import LoanDTO
from errors import (
    CreditLimitExceeded,
    InvalidSchema,
    LateInstallmentBlocksLoan,
    NotFoundAccount,
    NotFoundLoan,
)
from models import Loan, LoanInstallment, TransactionType
from repositories import AccountRepository, LoanRepository, TransactionRepository

BASIS_POINTS = Decimal(10000)


class LoanController(BaseController):
    """As regras de negócio do crédito: contratar, consultar e cobrar as parcelas."""

    def __init__(self) -> None:
        super().__init__(__name__)
        self.loan_repository = LoanRepository(self.context)
        self.account_repository = AccountRepository(self.context)
        self.transaction_repository = TransactionRepository(self.context)

    def create(self, account_key: str, loan_data: dict) -> tuple:
        """Contrata um crédito: credita o valor e gera as parcelas.

        A ordem das conferências é a regra:

          1. a conta do caminho é da equipe de quem pede (404 se não);
          2. a `idempotency_key` já foi usada? Então devolve o crédito
             original — ANTES de conferir o cargo. Quem contratou e
             depois passou a gestão adiante ainda precisa conseguir
             repetir o pedido e receber a mesma resposta;
          3. quem pede ocupa o cargo financeiro (403 se não);
          4. a conta é TRAVADA, e só então se lê o que decide o pedido:
             parcela em atraso, saldo médio e saldo devedor.

        A trava do passo 4 é o que impede duas contratações simultâneas
        de usarem o mesmo limite: a segunda espera o `commit` da
        primeira, e já encontra o saldo devedor novo.

        Devolve a tupla (crédito, criou?).
        """
        actor = self._get_actor()

        account = self.account_repository.get_by_key(account_key)

        if account is None or account.team_id != actor.team_id:
            raise NotFoundAccount(account_key)

        idempotency_key = loan_data["idempotency_key"]
        original = self.loan_repository.get_by_idempotency_key(account.id, idempotency_key)

        if original is not None:
            return self._original_to_dict(original), False

        self._require_finance(actor)

        account = self.account_repository.get_by_id_for_update(account.id)

        # A mesma pergunta, de novo, com a conta travada: duas cópias do
        # mesmo pedido chegando juntas passam as duas pela primeira.
        original = self.loan_repository.get_by_idempotency_key(account.id, idempotency_key)

        if original is not None:
            return self._original_to_dict(original), False

        if self.loan_repository.count_late_installments_by_account(account.id) > 0:
            raise LateInstallmentBlocksLoan()

        amount = loan_data["amount"]
        installments = loan_data["installments"]

        available_limit = self._available_credit_limit(account)

        if amount > available_limit:
            raise CreditLimitExceeded(amount, available_limit)

        # A taxa é a do plano de AGORA, e fica copiada no crédito.
        monthly_rate_bps = account.plan.loan_monthly_rate_bps
        installment_amount = self._price_installment(amount, monthly_rate_bps, installments)

        loan = self.loan_repository.create(
            account=account,
            requester=actor,
            principal=amount,
            monthly_rate_bps=monthly_rate_bps,
            installments=installments,
            installment_amount=installment_amount,
            purpose=loan_data["purpose"],
            idempotency_key=idempotency_key,
        )

        # A primeira parcela vence um mês depois da contratação.
        today = date.today()
        for number in range(1, installments + 1):
            self.loan_repository.add_installment(loan, number, self._add_months(today, number), installment_amount)

        transaction = self._register_movement(
            account,
            TransactionType.LOAN_DISBURSEMENT,
            amount,
            description=loan_data["purpose"],
            loan=loan,
        )

        # O flush manda tudo pro banco sem salvar: o DTO abaixo lê o
        # `created_at`, que é o banco quem preenche.
        self.session.flush()

        loan_dto = LoanDTO.contracted_to_dict(loan, transaction.balance_after)
        self.session.commit()

        return loan_dto, True

    def get_by_key(self, loan_key: str) -> dict:
        actor = self._get_actor()
        loan = self.loan_repository.get_by_key(loan_key)

        if loan is None or loan.account.team_id != actor.team_id:
            raise NotFoundLoan(loan_key)

        return LoanDTO.obj_to_dict(loan)

    def charge_due(self, charge_data: dict) -> dict:
        """Cobra as parcelas vencidas e não pagas. Chamada todo dia pelo agendador.

        Rota SEM sessão: quem a aciona é a infraestrutura, não um
        responsável.

        ────────────────────────────────────────────────────────────
        UMA TRANSAÇÃO POR PARCELA
        ────────────────────────────────────────────────────────────
        Repare que o `commit` está DENTRO do laço. Cada parcela é
        cobrada na própria transação, e isso é de propósito: com uma
        transação só para o lote, a falha na parcela de uma equipe
        desfaria a cobrança de todas as outras — e as travas de todas
        as contas ficariam presas até o lote inteiro terminar.

        ────────────────────────────────────────────────────────────
        POR QUE REPETIR NÃO COBRA DUAS VEZES
        ────────────────────────────────────────────────────────────
        O agendador pode disparar duas vezes (um retry, duas réplicas).
        Cada parcela é relida TRAVADA antes de ser cobrada, e parcela
        PAID é pulada. Duas execuções simultâneas entram em fila na
        trava da parcela; a segunda já lê PAID.

        A ordem das travas é a do resto do projeto: parcela, depois
        conta.

        ────────────────────────────────────────────────────────────
        SEM SALDO
        ────────────────────────────────────────────────────────────
        A parcela não é paga pela metade e não usa o `overdraft`: ela e
        o crédito passam a LATE, e a cobrança tenta de novo no dia
        seguinte. Enquanto houver parcela LATE, a conta não contrata
        crédito novo.
        """
        reference_date = self._parse_reference_date(charge_data)

        installment_ids = self.loan_repository.list_due_installment_ids(reference_date)

        # A consulta acima abriu uma transação; ela termina aqui pra que
        # cada parcela comece a sua do zero.
        self.session.commit()

        charged = 0
        late = 0

        for installment_id in installment_ids:
            installment = self.loan_repository.get_installment_for_update(installment_id)

            if installment is None or installment.status == LoanInstallment.PAID:
                self.session.rollback()
                continue

            loan = installment.loan
            account = self.account_repository.get_by_id_for_update(loan.account_id)

            if account.balance >= installment.amount:
                transaction = self._register_movement(
                    account,
                    TransactionType.LOAN_INSTALLMENT,
                    -installment.amount,
                    description=f"Parcela {installment.number}/{loan.installments}",
                    loan=loan,
                )
                self.loan_repository.mark_installment_paid(installment, transaction)
                charged = charged + 1
            else:
                self.loan_repository.mark_installment_late(installment)
                late = late + 1

            # O flush faz a contagem abaixo enxergar a parcela que
            # acabou de mudar.
            self.session.flush()
            self.loan_repository.update_status(loan, self._loan_status(loan))

            self.session.commit()

        self.logger.info(f"Cobrança de parcelas até {reference_date}: {charged} pagas, {late} em atraso")

        return {"charged": charged, "late": late}

    def _loan_status(self, loan: Loan) -> str:
        """O status do crédito, derivado das parcelas: LATE ganha de ACTIVE, e PAID é só quando acabou."""
        if self.loan_repository.count_installments(loan.id, LoanInstallment.LATE) > 0:
            return Loan.LATE

        if self.loan_repository.count_installments(loan.id, LoanInstallment.PAID) == loan.installments:
            return Loan.PAID

        return Loan.ACTIVE

    def _original_to_dict(self, loan: Loan) -> dict:
        """A resposta da repetição: o crédito original e o saldo de quando ele foi liberado."""
        disbursement = self.transaction_repository.get_by_loan_and_type(
            loan.id, TransactionType.LOAN_DISBURSEMENT
        )

        return LoanDTO.contracted_to_dict(loan, disbursement.balance_after)

    def _price_installment(self, principal: int, monthly_rate_bps: int, installments: int) -> int:
        """A parcela fixa da tabela Price, em centavos.

            parcela = principal × i / (1 − (1 + i)^−n)

        com `i` a taxa mensal e `n` o número de parcelas. Com taxa zero
        a fórmula divide por zero, e a parcela é só o principal dividido.

        A conta é feita em `Decimal`, e não em float: (1 + i)^n em
        ponto flutuante erra na última casa, e o erro viraria centavo
        na parcela de alguém. O resultado é arredondado UMA vez, no
        fim, para o centavo mais próximo. Todas as parcelas têm o mesmo
        valor.
        """
        rate = Decimal(monthly_rate_bps) / BASIS_POINTS

        if rate == 0:
            installment = Decimal(principal) / Decimal(installments)
        else:
            installment = Decimal(principal) * rate / (1 - (1 + rate) ** -installments)

        return int(installment.quantize(Decimal(1), rounding=ROUND_HALF_UP))

    def _add_months(self, start: date, months: int) -> date:
        """A mesma data, `months` meses depois — recuando pro fim do mês se o dia não existir.

        Quem contrata no dia 31 de janeiro não tem 31 de fevereiro: a
        parcela vence no último dia de fevereiro.
        """
        month_index = start.month - 1 + months
        year = start.year + month_index // 12
        month = month_index % 12 + 1
        day = min(start.day, calendar.monthrange(year, month)[1])

        return date(year, month, day)

    def _parse_reference_date(self, charge_data: dict) -> date:
        """A data de referência da cobrança: a do corpo, ou hoje.

        O schema garante o FORMATO (aaaa-mm-dd); o que ele não sabe é
        quantos dias fevereiro tem. "2026-02-30" chega aqui intacto, e
        é recusado com 400 em vez de virar 500.
        """
        if charge_data is None or charge_data.get("reference_date") is None:
            return date.today()

        try:
            return date.fromisoformat(charge_data["reference_date"])
        except ValueError:
            raise InvalidSchema(f"'{charge_data['reference_date']}' is not a real date in reference_date")
