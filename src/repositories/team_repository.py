from uuid import uuid4

from database import Context
from models import Team


class TeamRepository:
    """A camada que fala com o banco. Só aqui existe query.

    Nenhuma regra de negócio mora aqui: esta classe busca e guarda —
    quem decide o que fazer com isso é o controller.

    Como no base-service, ele recebe o CONTEXTO do trabalho, e tira a
    sessão de lá: `self.session = context.db_session`.
    """

    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def create(self, name: str, university: str) -> Team:
        team = Team()

        team.team_key = str(uuid4())
        team.name = name
        team.university = university

        self.session.add(team)
        return team

    def get_by_key(self, team_key: str) -> Team:
        return self.session.query(Team).filter(Team.team_key == team_key).first()

    def get_by_name_and_university(self, name: str, university: str) -> Team:
        return self.session.query(Team).filter(Team.name == name, Team.university == university).first()
