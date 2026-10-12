from datetime import date

from sqlalchemy.exc import IntegrityError

from controllers.base_controller import BaseController
from dtos import ExpenseDTO
from errors import (
    BudgetExceeded,
    CancelOnlyByRequester,
    ExpenseNotPending,
    InsufficientBalance,
    InvoiceAlreadyPaid,
    InvoiceAlreadyPending,
    NotFoundExpense,
    NotFoundSubsystem,
    NotFoundSupplier,
    NotFoundTeam,
)
from models import Account, Expense, ExpenseStatus, Member, TransactionType
from repositories import (
    AccountRepository,
    ExpenseRepository,
    SubsystemRepository,
    SupplierRepository,
    TeamRepository,
)
from utils.pagination import split_page

BASIS_POINTS = 10000


class ExpenseController(BaseController):
    """As regras de negócio do pedido de gasto — o controller mais cheio do projeto.

    Todo real que sai da conta passa por aqui, em dois tempos:

      • a SOLICITAÇÃO (`create`) reserva o valor no orçamento do
        subsistema — é o primeiro controle de saldo;
      • a APROVAÇÃO (`approve`) debita o valor e a tarifa da conta — é
        o segundo.

    Entre os dois, o pedido fica PENDING, com a reserva feita. Recusar
    (`reject`) ou cancelar (`cancel`) devolve a reserva.

    ────────────────────────────────────────────────────────────────
    A ORDEM DAS TRAVAS: PEDIDO → SUBSISTEMA → CONTA
    ────────────────────────────────────────────────────────────────
    Cada método aqui trava as linhas que vai ler pra decidir, e todos
    travam na MESMA ordem: primeiro o pedido, depois o subsistema,
    depois a conta. Nenhum pega a conta e depois pede o pedido.

    Isso é o que impede o impasse (deadlock): se a aprovação travasse
    pedido → conta e outra rota travasse conta → pedido, as duas
    poderiam ficar paradas pra sempre, cada uma segurando o que a outra
    quer. Com uma ordem só, quem chega depois espera — e quem chegou
    antes sempre consegue terminar.

    Nenhum método dá `commit` antes de gravar tudo: a trava vale
    enquanto a transação estiver aberta.
    """

    def __init__(self) -> None:
        super().__init__(__name__)
        self.expense_repository = ExpenseRepository(self.context)
        self.subsystem_repository = SubsystemRepository(self.context)
        self.supplier_repository = SupplierRepository(self.context)
        self.account_repository = AccountRepository(self.context)
        self.team_repository = TeamRepository(self.context)

    def create(self, expense_data: dict) -> tuple:
        """Registra o pedido e reserva o valor no subsistema.

        ────────────────────────────────────────────────────────────
        POR QUE A RESERVA É NA SOLICITAÇÃO, E COM O SUBSISTEMA TRAVADO
        ────────────────────────────────────────────────────────────
        Um subsistema com teto de R$ 1.000,00 e R$ 800,00 comprometidos,
        e dois pedidos de R$ 150,00 chegando juntos:

            pedido A: lê comprometido → 800. 800 + 150 cabe.
            pedido B: lê comprometido → 800. 800 + 150 cabe.
            pedido A: grava. Comprometido: 950.
            pedido B: grava. Comprometido: 1.100.

        Os dois perguntaram certo e os dois gravaram — e o teto estourou.
        O erro está no intervalo entre a pergunta e a gravação.

        A saída é travar o subsistema ANTES de ler o comprometido
        (`get_by_id_for_update`). O pedido B fica parado na trava até o
        A dar `commit`; aí lê 950, e 950 + 150 não cabe: 409.

        Se a reserva só acontecesse na aprovação, o teto seria
        descoberto tarde: dez pessoas pediriam, todas ouviriam "ok", e
        o financeiro é que descobriria que não cabe.

        Devolve a tupla (pedido, criou?): a repetição da mesma
        `idempotency_key` devolve o pedido original, sem reservar de
        novo.
        """
        actor = self._get_actor()

        idempotency_key = expense_data["idempotency_key"]
        amount = expense_data["amount"]
        invoice_number = expense_data.get("invoice_number")

        original = self.expense_repository.get_by_idempotency_key(actor.id, idempotency_key)

        if original is not None:
            return ExpenseDTO.only_obj_key(original), False

        subsystem = self.subsystem_repository.get_by_key(expense_data["subsystem_key"])

        if subsystem is None:
            raise NotFoundSubsystem(expense_data["subsystem_key"])

        self._require_same_team(actor, subsystem.team_id, "subsystem_key")

        supplier = self.supplier_repository.get_by_key(expense_data["supplier_key"])

        if supplier is None:
            raise NotFoundSupplier(expense_data["supplier_key"])

        self._require_same_team(actor, supplier.team_id, "supplier_key")

        account = self.account_repository.get_by_team(actor.team_id)

        # Daqui pra baixo, o subsistema é desta transação até o commit.
        locked_subsystem = self.subsystem_repository.get_by_id_for_update(subsystem.id)

        # A mesma pergunta de lá de cima, feita de novo com a trava na
        # mão: duas cópias do mesmo pedido chegando juntas passam as
        # duas pela primeira pergunta, e só uma passa por esta.
        original = self.expense_repository.get_by_idempotency_key(actor.id, idempotency_key)

        if original is not None:
            return ExpenseDTO.only_obj_key(original), False

        if invoice_number is not None:
            self._check_invoice_is_free(supplier.id, invoice_number)

        available = locked_subsystem.budget - locked_subsystem.committed

        if amount > available:
            raise BudgetExceeded(amount, available)

        self.subsystem_repository.reserve(locked_subsystem, amount)

        expense = self.expense_repository.create(
            account, locked_subsystem, supplier, actor, expense_data, self.request_id
        )

        requester_id = actor.id
        supplier_id = supplier.id

        try:
            self.session.flush()
        except IntegrityError as error:
            # O controller perguntou e o banco discordou: outra
            # requisição gravou no intervalo. O nome da restrição diz
            # qual das duas regras foi, e cada uma tem a sua resposta.
            constraint_name = self._violated_constraint(error)
            self.session.rollback()

            if constraint_name == "expense_requester_idempotency_key":
                original = self.expense_repository.get_by_idempotency_key(requester_id, idempotency_key)
                return ExpenseDTO.only_obj_key(original), False

            if constraint_name == "expense_open_invoice":
                self._check_invoice_is_free(supplier_id, invoice_number)
                raise InvoiceAlreadyPending(invoice_number)

            raise

        expense_dto = ExpenseDTO.only_obj_key(expense)
        self.session.commit()

        return expense_dto, True

    def get_by_key(self, expense_key: str) -> dict:
        actor = self._get_actor()
        expense = self.expense_repository.get_by_key(expense_key)

        if expense is None or expense.requester.team_id != actor.team_id:
            raise NotFoundExpense(expense_key)

        return ExpenseDTO.obj_to_dict(expense)

    def get_list(self, team_key: str, limit: int, offset: int, status_enumerators: list = None) -> dict:
        actor = self._get_actor()
        team = self.team_repository.get_by_key(team_key)

        if team is None or team.id != actor.team_id:
            raise NotFoundTeam(team_key)

        account = self.account_repository.get_by_team(team.id)

        expenses_list, is_last_page = split_page(
            self.expense_repository.list_page(account.id, limit, offset, status_enumerators), limit
        )

        return {
            "data": ExpenseDTO.list_obj_to_list_dict(expenses_list),
            "is_last_page": is_last_page,
        }

    def approve(self, expense_key: str) -> dict:
        """PENDING → PAID: debita o valor e a tarifa, e paga.

        Três conferências, cada uma com a linha que ela lê TRAVADA:

          1. o aprovador ocupa o cargo financeiro (403 se não);
          2. o pedido está PENDING (409 se não) — com o pedido travado.
             É isto que impede o pagamento em duplicidade: duas
             aprovações do mesmo pedido entram em fila na trava, e a
             segunda já lê PAID. Também impede o cruzamento com uma
             recusa: quem chegar depois encontra o pedido decidido;
          3. o saldo cobre valor + tarifa (409 se não) — com a conta
             travada. A tarifa é calculada DEPOIS da trava, porque
             depende do plano, e o plano pode estar sendo trocado.

        O pagamento NÃO usa o `overdraft`: a conta com saldo negativo
        (depois de uma passagem de gestão sem saldo) não paga pedido
        nenhum até as entradas cobrirem o descoberto.

        Na falta de saldo nada é gravado: o pedido continua PENDING, com
        a reserva no subsistema mantida, e pode ser aprovado de novo
        quando o dinheiro entrar.

        O pagamento e a tarifa viram DUAS linhas do extrato, cada uma
        com o seu `balance_after`. O `committed` do subsistema não muda:
        o que estava reservado agora está gasto, e continua contando no
        teto.
        """
        actor = self._get_actor()
        self._require_finance(actor)

        expense = self._get_locked_expense(actor, expense_key)
        self._check_is_pending(expense, ExpenseStatus.PAID)

        account = self.account_repository.get_by_id_for_update(expense.account_id)

        fee = self._outgoing_fee(account, expense.amount)
        required = expense.amount + fee

        if account.balance < required:
            raise InsufficientBalance(required)

        # Quem recebe: o fornecedor, na chave PIX dele — ou, no
        # reembolso, quem pagou do próprio bolso, na chave pessoal.
        if expense.kind == Expense.REIMBURSEMENT:
            transaction_type = TransactionType.REIMBURSEMENT
            counterparty_name = expense.requester.name
            counterparty_document = expense.requester.document_number
        else:
            transaction_type = TransactionType.SUPPLIER_PAYMENT
            counterparty_name = expense.supplier.name
            counterparty_document = expense.supplier.document_number

        self._register_movement(
            account,
            transaction_type,
            -expense.amount,
            counterparty_name=counterparty_name,
            counterparty_document=counterparty_document,
            description=expense.description,
            expense=expense,
            subsystem=expense.subsystem,
        )

        if fee > 0:
            self._register_movement(
                account,
                TransactionType.FEE,
                -fee,
                description=f"Tarifa de saída ({account.plan.enumerator})",
                expense=expense,
                subsystem=expense.subsystem,
            )

        self.expense_repository.update_decision(expense, actor)
        self.expense_repository.update_status(expense, ExpenseStatus.PAID, actor, self.request_id)

        expense_dto = ExpenseDTO.paid_to_dict(expense, fee, account.balance)
        self.session.commit()

        return expense_dto

    def reject(self, expense_key: str, reason: str) -> dict:
        """PENDING → REJECTED, pelo financeiro: devolve a reserva ao subsistema."""
        actor = self._get_actor()
        self._require_finance(actor)

        expense = self._get_locked_expense(actor, expense_key)
        self._check_is_pending(expense, ExpenseStatus.REJECTED)

        self._release_reservation(expense)

        self.expense_repository.update_decision(expense, actor, reason)
        self.expense_repository.update_status(expense, ExpenseStatus.REJECTED, actor, self.request_id)

        expense_dto = ExpenseDTO.only_obj_key(expense)
        self.session.commit()

        return expense_dto

    def cancel(self, expense_key: str) -> dict:
        """PENDING → CANCELED, por quem solicitou: devolve a reserva ao subsistema.

        Só o próprio solicitante cancela — nem o financeiro cancela o
        pedido de outro (pra isso existe a recusa, que registra quem
        decidiu e por quê).
        """
        actor = self._get_actor()

        expense = self._get_locked_expense(actor, expense_key)

        if expense.requester_member_id != actor.id:
            raise CancelOnlyByRequester()

        self._check_is_pending(expense, ExpenseStatus.CANCELED)

        self._release_reservation(expense)

        self.expense_repository.update_status(expense, ExpenseStatus.CANCELED, actor, self.request_id)

        expense_dto = ExpenseDTO.only_obj_key(expense)
        self.session.commit()

        return expense_dto

    def _get_locked_expense(self, actor: Member, expense_key: str) -> Expense:
        """O pedido, travado até o `commit` — a PRIMEIRA trava de toda decisão.

        Pedido de outra equipe responde o mesmo 404 de "não existe".
        """
        expense = self.expense_repository.get_by_key_for_update(expense_key)

        if expense is None or expense.requester.team_id != actor.team_id:
            raise NotFoundExpense(expense_key)

        return expense

    def _check_is_pending(self, expense: Expense, target_status: str) -> None:
        current_status = expense.status.enumerator

        if current_status != ExpenseStatus.PENDING:
            raise ExpenseNotPending(current_status, target_status)

    def _release_reservation(self, expense: Expense) -> None:
        """Devolve ao subsistema o valor que o pedido tinha reservado.

        O subsistema é a SEGUNDA trava (o pedido já está travado por
        quem chamou): a devolução é uma leitura seguida de uma gravação
        no `committed`, e um pedido novo no mesmo subsistema não pode
        ler o valor no meio dela.
        """
        locked_subsystem = self.subsystem_repository.get_by_id_for_update(expense.subsystem_id)

        self.subsystem_repository.release(locked_subsystem, expense.amount)

    def _check_invoice_is_free(self, supplier_id: int, invoice_number: str) -> None:
        """Recusa a nota fiscal que já está em um pedido pendente ou pago.

        Dois códigos, porque são duas situações pra quem chamou: nota
        em pedido PENDENTE pode voltar a ficar livre (se o pedido for
        recusado ou cancelado); nota PAGA não volta.
        """
        open_expense = self.expense_repository.get_open_by_invoice(supplier_id, invoice_number)

        if open_expense is None:
            return

        if open_expense.status.enumerator == ExpenseStatus.PAID:
            raise InvoiceAlreadyPaid(invoice_number)

        raise InvoiceAlreadyPending(invoice_number)

    def _outgoing_fee(self, account: Account, amount: int) -> int:
        """A tarifa de saída: max(valor × alíquota, mínimo) — ou zero na carência.

        Tudo em inteiros: centavos vezes pontos-base, dividido por
        10.000. Nenhum float entra na conta. O `+ BASIS_POINTS // 2`
        antes da divisão arredonda meio centavo pra cima; sem ele, a
        divisão inteira jogaria fora toda fração, sempre a favor do
        cliente.

        Quem chama já travou a conta: a alíquota lida aqui é a do plano
        que vale neste instante.
        """
        if date.today() <= account.grace_until:
            return 0

        proportional_fee = (amount * account.plan.outgoing_fee_bps + BASIS_POINTS // 2) // BASIS_POINTS

        return max(proportional_fee, account.plan.min_outgoing_fee)
