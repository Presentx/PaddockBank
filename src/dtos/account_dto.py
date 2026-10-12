from typing import List

from dtos.loan_dto import LoanDTO
from dtos.member_dto import MemberDTO
from models import Account, Loan, Member


class AccountDTO:
    """O JSON da conta."""

    @staticmethod
    def obj_to_dict(account: Account, holder: Member, available_credit_limit: int, open_loans: List[Loan]) -> dict:
        """A conta como o responsável a vê.

        O `balance` pode sair NEGATIVO: é o caso da tarifa de passagem
        de gestão cobrada sem saldo. `outgoing_fee_bps` é a alíquota da
        tarifa de saída do plano, em pontos-base (100 = 1%), e
        `grace_until` é o último dia sem tarifa nenhuma.

        O limite de crédito e os créditos em aberto não são colunas da
        conta: quem os calcula é o controller, e eles chegam aqui
        prontos — DTO não busca nada no banco.
        """
        dto = dict()
        dto["account_key"] = account.account_key
        dto["team_key"] = account.team.team_key
        dto["balance"] = account.balance
        dto["plan"] = account.plan.enumerator
        dto["outgoing_fee_bps"] = account.plan.outgoing_fee_bps
        dto["min_outgoing_fee"] = account.plan.min_outgoing_fee
        dto["pix_key"] = account.pix_key
        dto["holder"] = MemberDTO.obj_to_summary_dict(holder)
        dto["grace_until"] = account.grace_until.isoformat()
        dto["available_credit_limit"] = available_credit_limit
        dto["open_loans"] = LoanDTO.list_obj_to_list_dict(open_loans)

        return dto

    @staticmethod
    def plan_to_dict(account: Account) -> dict:
        dto = dict()
        dto["account_key"] = account.account_key
        dto["plan"] = account.plan.enumerator

        return dto
