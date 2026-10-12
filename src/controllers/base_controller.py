from abc import ABCMeta
from datetime import date, datetime, time, timedelta

from sqlalchemy.exc import IntegrityError

from constants import CREDIT_LIMIT_PERCENT, CREDIT_WINDOW_DAYS
from database import get_context
from errors import ForbiddenNotFinance, ForeignReference, InactiveMember, MissingIdentity
from models import Account, Member, MemberStatus, Transaction
from repositories import LoanRepository, MemberRepository, TransactionRepository
from utils.logger import get_logger
from utils.member_identity import get_member_key
from utils.request_context import get_request_id


class BaseController(metaclass=ABCMeta):
    """O que todo controller tem em comum: a conexão com o banco e o log.

    Nada chega por parâmetro: o controller pega o CONTEXTO da requisição
    em que está rodando. Quem preparou esse contexto foi o middleware.

    Guardar o `self.context`, e não só a sessão, é o que permite o
    repository receber `context` em vez de `db`: o contexto é a coisa que
    viaja entre as camadas, e a sessão é só o que ele carrega hoje.

    É aqui que a sessão nasce, no `get_or_create_session` — construir um
    controller é a mesma coisa que dizer "eu uso banco".

    ────────────────────────────────────────────────────────────────
    O QUE O PADDOCK BANK ACRESCENTOU AQUI
    ────────────────────────────────────────────────────────────────
    Três regras que valem para mais de um controller, e que por isso
    moram na classe-mãe em vez de serem copiadas:

      • QUEM está agindo (`_get_actor`, `_require_finance`,
        `_require_same_team`) — a regra de acesso de toda rota com
        sessão;
      • COMO o saldo muda (`_register_movement`) — o único lugar do
        projeto que escreve em `account.balance`;
      • QUANTO crédito a conta tem (`_available_credit_limit`) — usado
        na consulta da conta e na contratação.
    """

    def __init__(self, class_name: str) -> None:
        self.context = get_context()
        self.session = self.context.get_or_create_session()
        self.logger = get_logger(class_name)

        # O X-Request-ID desta requisição. Ele já aparece em toda linha
        # de log (veja utils/logger.py); aqui ele é guardado pra ser
        # gravado também nas linhas do extrato, no histórico dos pedidos
        # e nas passagens de gestão.
        self.request_id = get_request_id()

    # ────────────────────────────────────────────────────────────────
    # Quem está agindo
    # ────────────────────────────────────────────────────────────────
    def _get_actor(self) -> Member:
        """O responsável que está agindo nesta requisição.

        A `member_key` vem do contexto, onde o middleware de identidade
        a deixou (src/middlewares/member_identity.py) — nunca do corpo.

        Sem identidade, com uma chave fora do formato ou com uma chave
        que não é de ninguém, a resposta é a mesma: 401. Não se diz
        "essa chave não existe" a quem não provou quem é.
        """
        member_key = get_member_key()

        if member_key is None:
            raise MissingIdentity()

        actor = MemberRepository(self.context).get_by_key(member_key)

        if actor is None:
            raise MissingIdentity()

        if actor.status.enumerator != MemberStatus.ACTIVE:
            raise InactiveMember(actor.member_key)

        return actor

    def _require_finance(self, actor: Member) -> None:
        """Recusa com 403 quem não ocupa o cargo financeiro da própria equipe."""
        if not actor.role.is_finance:
            raise ForbiddenNotFinance()

    def _require_same_team(self, actor: Member, team_id: int, field: str) -> None:
        """Recusa com 422 uma referência DO CORPO a recurso de outra equipe.

        Só para chaves que vieram no corpo. Recurso do CAMINHO que é de
        outra equipe responde o 404 do próprio recurso — e essa
        conferência cada controller faz ao buscar o recurso, junto com o
        "não existe", pra que os dois casos sejam indistinguíveis.
        """
        if team_id != actor.team_id:
            raise ForeignReference(field)

    # ────────────────────────────────────────────────────────────────
    # Como o saldo muda
    # ────────────────────────────────────────────────────────────────
    def _register_movement(
        self,
        account: Account,
        type_enumerator: str,
        amount: int,
        allow_overdraft: bool = False,
        **transaction_fields,
    ) -> Transaction:
        """Muda o saldo da conta E grava a linha do extrato — sempre os dois.

        É o único lugar do projeto que escreve em `account.balance`, e
        por isso a regra "a soma do extrato é o saldo" não depende de
        ninguém lembrar: não existe caminho que mexa num sem mexer no
        outro.

        `amount` tem sinal: crédito positivo, débito negativo.

        QUEM CHAMA JÁ TRAVOU A CONTA (`..._for_update`) e, se for
        débito, já conferiu que o saldo cobre. Este método não confere
        saldo: quem sabe se o pedido pode ser recusado é a regra de
        cada operação.

        ────────────────────────────────────────────────────────────
        O OVERDRAFT
        ────────────────────────────────────────────────────────────
        Só a tarifa de passagem de gestão chama com
        `allow_overdraft=True`. Nesse caso, se o saldo ficar negativo, o
        valor descoberto é gravado em `overdraft` — e é isso que faz o
        CHECK do banco (balance >= -overdraft) aceitar a linha.

        Em qualquer CRÉDITO, o `overdraft` é recalculado para o que
        ainda falta cobrir: as entradas seguintes compensam o
        descoberto, e a autorização de saldo negativo some junto com
        ele. Sem isso, a conta voltaria a ter saldo e continuaria com
        uma permissão de negativo que nenhuma regra concedeu.
        """
        new_balance = account.balance + amount

        if allow_overdraft and new_balance < 0:
            account.overdraft = -new_balance
        elif amount > 0:
            account.overdraft = max(0, -new_balance)

        account.balance = new_balance

        return TransactionRepository(self.context).create(
            account=account,
            type_enumerator=type_enumerator,
            amount=amount,
            balance_after=new_balance,
            request_id=self.request_id,
            **transaction_fields,
        )

    # ────────────────────────────────────────────────────────────────
    # Quanto crédito a conta tem
    # ────────────────────────────────────────────────────────────────
    def _available_credit_limit(self, account: Account) -> int:
        """50% do saldo médio diário de 90 dias, menos o saldo devedor.

        O saldo devedor é a soma das parcelas ainda não pagas (com os
        juros). O limite nunca sai negativo: quem deve mais do que o
        limite tem limite zero, não "limite negativo".
        """
        average_balance = self._average_daily_balance(account)
        outstanding_debt = LoanRepository(self.context).sum_unpaid_installments_by_account(account.id)

        available_limit = average_balance * CREDIT_LIMIT_PERCENT // 100 - outstanding_debt

        return max(0, available_limit)

    def _average_daily_balance(self, account: Account) -> int:
        """A média do saldo de FECHAMENTO de cada dia da janela.

        A janela são os últimos CREDIT_WINDOW_DAYS dias, contando hoje.
        O saldo de fechamento de um dia é o `balance_after` da última
        linha do extrato até aquele dia; antes da primeira linha da
        conta, é zero.

        É por isso que o limite mede o dinheiro que PERMANECE: R$
        9.000,00 depositados hoje numa conta nova pesam um dia em
        noventa — saldo médio de R$ 100,00, limite de R$ 50,00. O mesmo
        valor parado há três meses dá limite de R$ 4.500,00.

        A conta é feita no extrato, que é append-only: não existe uma
        tabela de saldo diário pra manter em dia.
        """
        transaction_repository = TransactionRepository(self.context)

        window_start = date.today() - timedelta(days=CREDIT_WINDOW_DAYS - 1)
        window_start_moment = datetime.combine(window_start, time.min)

        closing_balance = 0
        last_before_window = transaction_repository.get_last_before(account.id, window_start_moment)
        if last_before_window is not None:
            closing_balance = last_before_window.balance_after

        transactions = transaction_repository.list_since(account.id, window_start_moment)

        total = 0
        index = 0

        for day_offset in range(CREDIT_WINDOW_DAYS):
            day = window_start + timedelta(days=day_offset)

            while index < len(transactions) and transactions[index].created_at.date() <= day:
                closing_balance = transactions[index].balance_after
                index = index + 1

            total = total + closing_balance

        return total // CREDIT_WINDOW_DAYS

    # ────────────────────────────────────────────────────────────────
    # Quando o banco recusa o que o controller deixou passar
    # ────────────────────────────────────────────────────────────────
    def _flush_or_conflict(self, conflicts: dict) -> None:
        """Manda as escritas pro banco e traduz a restrição violada em erro nosso.

        Todo cadastro confere a duplicidade ANTES de gravar ("já existe
        um cargo com este nome?"), e isso resolve o caso comum. Mas
        entre a pergunta e a gravação existe um intervalo: duas
        requisições simultâneas perguntam, as duas ouvem "não existe", e
        as duas gravam. Quem pega a segunda é o UNIQUE do banco.

        Sem este método, essa violação subiria como IntegrityError até o
        handler genérico e sairia como 500 — a API assumindo a culpa por
        um conflito que tem nome. Aqui ela vira o mesmo 409 que a
        conferência teria dado.

        `conflicts` liga o NOME da restrição (escrito no
        database/database.sql) ao erro que ela significa. Restrição que
        não está no dicionário continua subindo: essa sim é um bug.

        O `rollback` antes do `raise` não é opcional: depois de um erro,
        o Postgres recusa qualquer comando na mesma transação.
        """
        try:
            self.session.flush()
        except IntegrityError as error:
            constraint_name = self._violated_constraint(error)
            self.session.rollback()

            if constraint_name in conflicts:
                raise conflicts[constraint_name]

            raise

    @staticmethod
    def _violated_constraint(error: IntegrityError) -> str:
        """O nome da restrição que o banco disse ter sido violada, ou None."""
        diagnostics = getattr(error.orig, "diag", None)

        return getattr(diagnostics, "constraint_name", None)
