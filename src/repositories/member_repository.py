from uuid import uuid4

from database import Context
from models import Member, MemberStatus, Role, Team


class MemberRepository:
    """As consultas dos responsáveis.

    Repare que as buscas por CPF e por e-mail levam o `team_id`: os dois
    são únicos POR EQUIPE, então a pergunta "já existe?" só faz sentido
    dentro de uma equipe.
    """

    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def create(self, team: Team, role: Role, member_data: dict) -> Member:
        member = Member()

        member.member_key = str(uuid4())
        member.team_id = team.id
        member.role = role
        member.status = self.get_status(MemberStatus.ACTIVE)
        member.name = member_data["name"]
        member.document_number = member_data["document_number"]
        member.email = member_data["email"]
        member.phone = member_data["phone"]
        member.pix_key = member_data["pix_key"]

        self.session.add(member)
        return member

    def update_contact(self, member: Member, member_data: dict) -> None:
        """Atualiza só os campos de contato que vieram no pedido."""
        for field in ["name", "email", "phone", "pix_key"]:
            if field in member_data:
                setattr(member, field, member_data[field])

    def update_role(self, member: Member, role: Role) -> None:
        member.role = role

    def update_status(self, member: Member, new_status_enumerator: str) -> None:
        member.status = self.get_status(new_status_enumerator)

    def get_status(self, enumerator: str) -> MemberStatus:
        return self.session.query(MemberStatus).filter(MemberStatus.enumerator == enumerator).one()

    def get_by_key(self, member_key: str) -> Member:
        return self.session.query(Member).filter(Member.member_key == member_key).first()

    def get_by_document_number(self, team_id: int, document_number: str) -> Member:
        return (
            self.session.query(Member)
            .filter(Member.team_id == team_id, Member.document_number == document_number)
            .first()
        )

    def get_by_email(self, team_id: int, email: str) -> Member:
        return self.session.query(Member).filter(Member.team_id == team_id, Member.email == email).first()

    def get_finance_member(self, team_id: int) -> Member:
        """O titular da conta: quem ocupa o cargo financeiro da equipe."""
        return (
            self.session.query(Member)
            .join(Member.role)
            .filter(Member.team_id == team_id, Role.is_finance.is_(True))
            .first()
        )

    def list_page(self, team_id: int, limit: int, offset: int, role: Role = None) -> list:
        query = self.session.query(Member).filter(Member.team_id == team_id)

        if role is not None:
            query = query.filter(Member.role_id == role.id)

        query = query.order_by(Member.created_at.desc(), Member.id.desc())

        return query.limit(limit + 1).offset(offset).all()
