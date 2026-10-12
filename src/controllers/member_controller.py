from controllers.base_controller import BaseController
from dtos import MemberDTO
from errors import (
    DuplicatedMemberDocument,
    DuplicatedMemberEmail,
    FinanceMemberCannotBeDeactivated,
    FinanceRoleOnlyByHandover,
    InvalidCpf,
    NotFoundMember,
    NotFoundRole,
    NotFoundTeam,
)
from models import Member, MemberStatus, Role, Team
from repositories import MemberRepository, RoleRepository, TeamRepository
from utils.document_number import is_valid_cpf
from utils.pagination import split_page


class MemberController(BaseController):
    """As regras de negócio dos responsáveis.

    Uma regra atravessa tudo aqui: o cargo financeiro só muda de mãos
    pela passagem de gestão (HandoverController). Por isso este
    controller recusa pôr alguém nele, tirar alguém dele e desativar
    quem o ocupa — as três seriam trocas de titular da conta sem
    registro e sem tarifa.
    """

    def __init__(self) -> None:
        super().__init__(__name__)
        self.member_repository = MemberRepository(self.context)
        self.role_repository = RoleRepository(self.context)
        self.team_repository = TeamRepository(self.context)

    def create(self, team_key: str, member_data: dict) -> dict:
        """Cadastra um responsável, conferindo o CPF, o cargo e as duplicidades.

        O schema já cobrou a máscara do CPF (400). Aqui se confere o
        que só se sabe fazendo a conta ou olhando o banco: os dígitos
        verificadores (422), se o cargo existe e é desta equipe, e se o
        CPF ou o e-mail já estão na equipe (409).
        """
        actor = self._get_actor()
        self._require_finance(actor)
        team = self._get_team(actor, team_key)

        document_number = member_data["document_number"]
        email = member_data["email"]

        if not is_valid_cpf(document_number):
            raise InvalidCpf()

        role = self._get_referenced_role(actor, member_data["role_key"])

        if role.is_finance:
            raise FinanceRoleOnlyByHandover()

        if self.member_repository.get_by_document_number(team.id, document_number) is not None:
            raise DuplicatedMemberDocument()

        if self.member_repository.get_by_email(team.id, email) is not None:
            raise DuplicatedMemberEmail()

        member = self.member_repository.create(team, role, member_data)

        self._flush_or_conflict(
            {
                "member_team_document_number_key": DuplicatedMemberDocument(),
                "member_team_email_key": DuplicatedMemberEmail(),
            }
        )

        member_dto = MemberDTO.only_obj_key(member)
        self.session.commit()

        return member_dto

    def update(self, member_key: str, member_data: dict) -> dict:
        """Altera contato, cargo ou situação de um responsável.

        Todas as conferências vêm ANTES de qualquer escrita: um pedido
        que troca o e-mail e o cargo e é recusado pelo cargo não pode
        deixar o e-mail trocado.

        O CPF não muda — ele não está nem no schema. CPF errado é outro
        responsável.
        """
        actor = self._get_actor()
        self._require_finance(actor)
        member = self._get_member(actor, member_key)

        new_role = None

        if "role_key" in member_data:
            new_role = self._get_referenced_role(actor, member_data["role_key"])

            if new_role.id != member.role_id and (new_role.is_finance or member.role.is_finance):
                raise FinanceRoleOnlyByHandover()

        if member_data.get("active") is False and member.role.is_finance:
            raise FinanceMemberCannotBeDeactivated()

        if "email" in member_data and member_data["email"] != member.email:
            if self.member_repository.get_by_email(member.team_id, member_data["email"]) is not None:
                raise DuplicatedMemberEmail()

        self.member_repository.update_contact(member, member_data)

        if new_role is not None:
            self.member_repository.update_role(member, new_role)

        if "active" in member_data:
            if member_data["active"]:
                self.member_repository.update_status(member, MemberStatus.ACTIVE)
            else:
                self.member_repository.update_status(member, MemberStatus.INACTIVE)

        self._flush_or_conflict({"member_team_email_key": DuplicatedMemberEmail()})

        member_dto = MemberDTO.obj_to_dict(member)
        self.session.commit()

        return member_dto

    def get_by_key(self, member_key: str) -> dict:
        actor = self._get_actor()
        member = self._get_member(actor, member_key)

        return MemberDTO.obj_to_dict(member)

    def get_list(self, team_key: str, limit: int, offset: int, role_key: str = None) -> dict:
        """A página pedida, com o filtro de cargo se ele vier.

        Filtrar por um cargo que não existe (ou que é de outra equipe)
        responde 404, e não uma lista vazia: lista vazia diria "ninguém
        ocupa esse cargo", e a verdade é que a pergunta não tinha
        resposta possível.
        """
        actor = self._get_actor()
        team = self._get_team(actor, team_key)

        role = None

        if role_key is not None:
            role = self.role_repository.get_by_key(role_key)

            if role is None or role.team_id != team.id:
                raise NotFoundRole(role_key)

        members_list, is_last_page = split_page(
            self.member_repository.list_page(team.id, limit, offset, role), limit
        )

        return {
            "data": MemberDTO.list_obj_to_list_dict(members_list),
            "is_last_page": is_last_page,
        }

    def _get_team(self, actor: Member, team_key: str) -> Team:
        team = self.team_repository.get_by_key(team_key)

        if team is None or team.id != actor.team_id:
            raise NotFoundTeam(team_key)

        return team

    def _get_member(self, actor: Member, member_key: str) -> Member:
        member = self.member_repository.get_by_key(member_key)

        if member is None or member.team_id != actor.team_id:
            raise NotFoundMember(member_key)

        return member

    def _get_referenced_role(self, actor: Member, role_key: str) -> Role:
        role = self.role_repository.get_by_key(role_key)

        if role is None:
            raise NotFoundRole(role_key)

        self._require_same_team(actor, role.team_id, "role_key")

        return role
