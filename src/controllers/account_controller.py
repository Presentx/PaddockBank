from controllers.base_controller import BaseController
from dtos import AccountDTO, TransactionDTO
from errors import NotFoundAccount, NotFoundPixKey, NotFoundSubsystem
from models import Account, Member, TransactionType
from repositories import (
    AccountRepository,
    LoanRepository,
    MemberRepository,
    SubsystemRepository,
    TransactionRepository,
)
from utils.pagination import split_page


class AccountController(BaseController):
    """As regras de negócio da conta: consulta, plano, depósito e extrato."""

    def __init__(self) -> None:
        super().__init__(__name__)
        self.account_repository = AccountRepository(self.context)
        self.member_repository = MemberRepository(self.context)
        self.loan_repository = LoanRepository(self.context)
        self.subsystem_repository = SubsystemRepository(self.context)
        self.transaction_repository = TransactionRepository(self.context)

    def get_by_key(self, account_key: str) -> dict:
        actor = self._get_actor()
        account = self._get_account(actor, account_key)

        holder = self.member_repository.get_finance_member(account.team_id)
        available_credit_limit = self._available_credit_limit(account)
        open_loans = self.loan_repository.list_open_by_account(account.id)

        return AccountDTO.obj_to_dict(account, holder, available_credit_limit, open_loans)

    def update_plan(self, account_key: str, plan_enumerator: str) -> dict:
        """Troca o plano da conta.

        A conta é travada porque o plano decide a tarifa: uma aprovação
        de gasto lê o plano com a conta travada, e a troca precisa
        entrar na mesma fila — antes ou depois do pagamento, nunca no
        meio dele.

        Trocar de plano não mexe no que já aconteceu: tarifa já cobrada
        continua cobrada, e crédito já contratado continua com a taxa
        do dia da contratação. A cobrança da mensalidade Pro está fora
        do escopo desta entrega.
        """
        actor = self._get_actor()
        self._require_finance(actor)
        account = self._get_account(actor, account_key)

        account = self.account_repository.get_by_id_for_update(account.id)
        plan = self.account_repository.get_plan(plan_enumerator)

        self.account_repository.update_plan(account, plan)

        account_dto = AccountDTO.plan_to_dict(account)
        self.session.commit()

        return account_dto

    def deposit(self, pix_key: str, deposit_data: dict) -> tuple:
        """Credita uma entrada na conta dona da chave PIX.

        Rota SEM sessão: quem a chama não é um responsável da equipe, é
        o arranjo de pagamentos avisando que o dinheiro chegou. A conta
        é achada pela chave PIX, a única porta de entrada de recursos.

        ────────────────────────────────────────────────────────────
        POR QUE A CHAVE DE IDEMPOTÊNCIA É CONFERIDA COM A CONTA TRAVADA
        ────────────────────────────────────────────────────────────
        Aviso de pagamento é o tipo de requisição que se repete: a rede
        cai antes da resposta, e quem chamou manda de novo. Sem
        proteção, o mesmo PIX seria creditado duas vezes.

        A conferência "já vi esta chave?" é uma leitura seguida de uma
        gravação, e o perigo mora entre as duas: duas cópias do mesmo
        aviso chegando juntas, as duas lendo "nunca vi", as duas
        creditando. Travando a conta ANTES de perguntar, a segunda
        cópia espera a primeira dar `commit` — e aí encontra a linha, e
        devolve a transação original.

        Devolve a tupla (comprovante, criou?), e é o resource que
        traduz o segundo valor em 201 ou 200.
        """
        account = self.account_repository.get_by_pix_key_for_update(pix_key)

        if account is None:
            raise NotFoundPixKey(pix_key)

        idempotency_key = deposit_data["idempotency_key"]
        original = self.transaction_repository.get_by_idempotency_key(account.id, idempotency_key)

        if original is not None:
            return TransactionDTO.receipt_to_dict(original), False

        transaction = self._register_movement(
            account,
            TransactionType.DEPOSIT,
            deposit_data["amount"],
            counterparty_name=deposit_data["payer_name"],
            counterparty_document=deposit_data["payer_document"],
            description=deposit_data.get("description"),
            idempotency_key=idempotency_key,
        )

        receipt_dto = TransactionDTO.receipt_to_dict(transaction)
        self.session.commit()

        return receipt_dto, True

    def get_statement(self, account_key: str, limit: int, offset: int, subsystem_key: str = None) -> dict:
        """O extrato, da linha mais nova para a mais antiga.

        Consulta não trava nada: quem lê o extrato não espera quem está
        pagando, e vice-versa.
        """
        actor = self._get_actor()
        account = self._get_account(actor, account_key)

        subsystem = None

        if subsystem_key is not None:
            subsystem = self.subsystem_repository.get_by_key(subsystem_key)

            if subsystem is None or subsystem.team_id != account.team_id:
                raise NotFoundSubsystem(subsystem_key)

        transactions_list, is_last_page = split_page(
            self.transaction_repository.list_page(account.id, limit, offset, subsystem), limit
        )

        return {
            "data": TransactionDTO.list_obj_to_list_dict(transactions_list),
            "is_last_page": is_last_page,
        }

    def _get_account(self, actor: Member, account_key: str) -> Account:
        """A conta do caminho — ou 404, exista ela ou não, se não for a da equipe do ator."""
        account = self.account_repository.get_by_key(account_key)

        if account is None or account.team_id != actor.team_id:
            raise NotFoundAccount(account_key)

        return account
