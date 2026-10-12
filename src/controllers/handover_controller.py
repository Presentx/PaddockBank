from datetime import date

from controllers.base_controller import BaseController
from dtos import HandoverDTO
from errors import (
    FinanceRoleOnlyByHandover,
    InactiveMember,
    MemberAlreadyFinance,
    NotFoundMember,
    NotFoundRole,
    NotFoundTeam,
)
from models import Account, Handover, MemberStatus, TransactionType
from repositories import (
    AccountRepository,
    HandoverRepository,
    MemberRepository,
    RoleRepository,
    TeamRepository,
)


class HandoverController(BaseController):
    """A passagem de gestão: a troca do responsável financeiro.

    É a operação que responde à dor central do Paddock Bank — a
    diretoria muda todo ano, e o controle não pode se perder na troca.
    Aqui a troca é UMA transação: o cargo financeiro muda de mãos, a
    titularidade da conta vai junto, e fica um registro de quem saiu e
    quem entrou. A conta, a chave PIX, o extrato e os pedidos pendentes
    continuam exatamente onde estavam.
    """

    def __init__(self) -> None:
        super().__init__(__name__)
        self.team_repository = TeamRepository(self.context)
        self.account_repository = AccountRepository(self.context)
        self.member_repository = MemberRepository(self.context)
        self.role_repository = RoleRepository(self.context)
        self.handover_repository = HandoverRepository(self.context)

    def create(self, team_key: str, handover_data: dict) -> dict:
        """Transfere o cargo financeiro para o sucessor.

        ────────────────────────────────────────────────────────────
        A IDEMPOTÊNCIA VEM ANTES DA CONFERÊNCIA DO CARGO — E SOB A TRAVA
        ────────────────────────────────────────────────────────────
        Esta rota tem uma particularidade: depois que ela dá certo,
        quem a chamou NÃO é mais o financeiro. Se a resposta se perder
        na rede e ele repetir o pedido, a conferência "você ocupa o
        cargo financeiro?" responderia 403 — pra um pedido que já foi
        atendido.

        Por isso a ordem é: trava a conta, procura a `idempotency_key`
        e, se achar, devolve o resultado original; só DEPOIS confere o
        cargo. A repetição não cobra de novo nem troca os cargos de
        volta.

        A conta é travada antes da procura pelo mesmo motivo do
        depósito: duas cópias do mesmo pedido chegando juntas entram em
        fila, e a segunda já encontra a passagem gravada.

        ────────────────────────────────────────────────────────────
        A TARIFA, E O ÚNICO SALDO NEGATIVO DO SISTEMA
        ────────────────────────────────────────────────────────────
        No plano FREE, depois da carência, a passagem tem tarifa — e
        ela é cobrada MESMO SEM SALDO. É a única operação que pode
        deixar a conta negativa (`allow_overdraft=True`): a equipe que
        troca de gestão com o caixa zerado não fica impedida de trocar,
        e a tarifa é compensada pelas entradas seguintes. Enquanto
        estiver negativa, a conta não paga pedidos.

        No plano PRO a tarifa é zero, e na carência também: nesses
        casos não nasce linha no extrato.
        """
        actor = self._get_actor()

        team = self.team_repository.get_by_key(team_key)

        if team is None or team.id != actor.team_id:
            raise NotFoundTeam(team_key)

        account = self.account_repository.get_by_team(team.id)
        account = self.account_repository.get_by_id_for_update(account.id)

        original = self.handover_repository.get_by_idempotency_key(account.id, handover_data["idempotency_key"])

        if original is not None:
            return HandoverDTO.obj_to_dict(original, self._balance_after(original, account))

        self._require_finance(actor)

        incoming_member = self.member_repository.get_by_key(handover_data["incoming_member_key"])

        if incoming_member is None:
            raise NotFoundMember(handover_data["incoming_member_key"])

        self._require_same_team(actor, incoming_member.team_id, "incoming_member_key")

        if incoming_member.status.enumerator != MemberStatus.ACTIVE:
            raise InactiveMember(incoming_member.member_key)

        if incoming_member.role.is_finance:
            raise MemberAlreadyFinance(incoming_member.member_key)

        outgoing_role = self.role_repository.get_by_key(handover_data["outgoing_role_key"])

        if outgoing_role is None:
            raise NotFoundRole(handover_data["outgoing_role_key"])

        self._require_same_team(actor, outgoing_role.team_id, "outgoing_role_key")

        # O cargo de saída é pra onde vai quem está deixando o
        # financeiro. Se fosse o próprio cargo financeiro, a equipe
        # terminaria a passagem com dois titulares.
        if outgoing_role.is_finance:
            raise FinanceRoleOnlyByHandover()

        fee = self._handover_fee(account)
        transaction = None

        if fee > 0:
            transaction = self._register_movement(
                account,
                TransactionType.HANDOVER_FEE,
                -fee,
                allow_overdraft=True,
                description=f"Tarifa de passagem de gestão ({account.plan.enumerator})",
            )

        # A troca: o sucessor assume o cargo financeiro, e quem sai vai
        # pro cargo que indicou.
        finance_role = actor.role
        self.member_repository.update_role(incoming_member, finance_role)
        self.member_repository.update_role(actor, outgoing_role)

        handover = self.handover_repository.create(
            account=account,
            outgoing_member=actor,
            incoming_member=incoming_member,
            fee=fee,
            transaction=transaction,
            idempotency_key=handover_data["idempotency_key"],
            request_id=self.request_id,
        )

        handover_dto = HandoverDTO.obj_to_dict(handover, account.balance)
        self.session.commit()

        return handover_dto

    def _handover_fee(self, account: Account) -> int:
        """A tarifa de passagem do plano — ou zero, na carência.

        Quem chama já travou a conta: o plano lido aqui é o que vale
        neste instante.
        """
        if date.today() <= account.grace_until:
            return 0

        return account.plan.handover_fee

    def _balance_after(self, handover: Handover, account: Account) -> int:
        """O saldo que a passagem deixou, para a resposta da repetição.

        Quando houve tarifa, é o `balance_after` da linha HANDOVER_FEE
        do extrato — o saldo daquele instante, não o de agora. Quando a
        passagem foi isenta, ela não tem linha e não mexeu no saldo:
        vale o saldo atual da conta.
        """
        if handover.transaction is not None:
            return handover.transaction.balance_after

        return account.balance
