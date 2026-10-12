from dtos.member_dto import MemberDTO
from models import Account, Member, Role, Team


class TeamDTO:
    """O JSON da equipe."""

    @staticmethod
    def obj_to_dict(team: Team, account: Account, finance_member: Member) -> dict:
        """A equipe, a conta dela e quem é o responsável financeiro.

        Da conta vai só o que serve pra chegar nela — a chave e a chave
        PIX. Saldo, plano e limite ficam no GET /account/{account_key}.
        """
        dto = dict()
        dto["team_key"] = team.team_key
        dto["name"] = team.name
        dto["university"] = team.university
        dto["created_at"] = team.created_at.isoformat()
        dto["account"] = {
            "account_key": account.account_key,
            "pix_key": account.pix_key,
            "plan": account.plan.enumerator,
        }
        dto["finance_member"] = MemberDTO.obj_to_summary_dict(finance_member)
        dto["finance_member"]["role_key"] = finance_member.role.role_key

        return dto

    @staticmethod
    def created_to_dict(team: Team, account: Account, finance_role: Role, finance_member: Member) -> dict:
        """As cinco chaves que nascem no cadastro da equipe."""
        dto = dict()
        dto["team_key"] = team.team_key
        dto["account_key"] = account.account_key
        dto["pix_key"] = account.pix_key
        dto["finance_role_key"] = finance_role.role_key
        dto["member_key"] = finance_member.member_key

        return dto
