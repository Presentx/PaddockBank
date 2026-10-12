from datetime import date, timedelta

from constants import DEFAULT_FINANCE_ROLE_NAME, GRACE_PERIOD_DAYS
from controllers.base_controller import BaseController
from dtos import TeamDTO
from errors import DuplicatedTeam, InvalidCpf, NotFoundTeam
from models import Plan
from repositories import AccountRepository, MemberRepository, RoleRepository, TeamRepository
from utils.document_number import is_valid_cpf


class TeamController(BaseController):
    """As regras de negócio da equipe. Aqui mora o "pode" e o "não pode"."""

    def __init__(self) -> None:
        super().__init__(__name__)
        self.team_repository = TeamRepository(self.context)
        self.account_repository = AccountRepository(self.context)
        self.role_repository = RoleRepository(self.context)
        self.member_repository = MemberRepository(self.context)

    def create(self, team_data: dict) -> dict:
        """Cadastra a equipe e tudo o que ela precisa pra existir — de uma vez.

        Quatro linhas nascem na MESMA transação: a equipe, a conta, o
        cargo financeiro e o responsável que o ocupa. Uma equipe sem
        conta, ou uma conta sem titular, é um estado que este sistema
        não sabe tratar — então ele não pode existir nem por um
        instante. Se qualquer passo falhar, o `commit` não acontece e
        nada fica gravado.

        Esta é uma das três rotas SEM sessão: ainda não existe
        responsável nenhum pra se identificar. O primeiro nasce aqui.

        A conta começa no plano FREE, com saldo zero e carência de
        GRACE_PERIOD_DAYS dias — até `grace_until`, nenhuma tarifa é
        cobrada.
        """
        self.logger.debug("Cadastrando uma nova equipe")

        name = team_data["name"]
        university = team_data["university"]
        treasurer_data = team_data["treasurer"]
        finance_role_name = team_data.get("finance_role_name", DEFAULT_FINANCE_ROLE_NAME)

        if not is_valid_cpf(treasurer_data["document_number"]):
            raise InvalidCpf()

        if self.team_repository.get_by_name_and_university(name, university) is not None:
            raise DuplicatedTeam()

        team = self.team_repository.create(name, university)

        # O flush manda a equipe pro banco sem salvar: é o que dá a ela
        # um `id`, de que o cargo e o responsável precisam. E é aqui que
        # o UNIQUE(name, university) pega dois cadastros simultâneos.
        self._flush_or_conflict({"team_name_university_key": DuplicatedTeam()})

        plan = self.account_repository.get_plan(Plan.FREE)
        grace_until = date.today() + timedelta(days=GRACE_PERIOD_DAYS)
        account = self.account_repository.create(team, plan, grace_until)

        finance_role = self.role_repository.create(team, finance_role_name, parent=None, is_finance=True)
        finance_member = self.member_repository.create(team, finance_role, treasurer_data)

        team_dto = TeamDTO.created_to_dict(team, account, finance_role, finance_member)

        self.session.commit()

        return team_dto

    def get_by_key(self, team_key: str) -> dict:
        actor = self._get_actor()
        team = self._get_team(actor, team_key)

        account = self.account_repository.get_by_team(team.id)
        finance_member = self.member_repository.get_finance_member(team.id)

        return TeamDTO.obj_to_dict(team, account, finance_member)

    def _get_team(self, actor, team_key: str):
        """A equipe do caminho — ou 404, exista ela ou não, se não for a do ator."""
        team = self.team_repository.get_by_key(team_key)

        if team is None or team.id != actor.team_id:
            raise NotFoundTeam(team_key)

        return team
