from datetime import date
from uuid import uuid4

from database import Context
from models import Account, Plan, Team


class AccountRepository:
    """As consultas da conta e do plano dela.

    ────────────────────────────────────────────────────────────────
    OS TRÊS `..._for_update` E O `populate_existing`
    ────────────────────────────────────────────────────────────────
    `with_for_update()` vira `SELECT ... FOR UPDATE`: a linha da conta
    fica reservada pra esta transação até o `commit` (ou o `rollback`).
    Outra requisição que peça a MESMA conta do mesmo jeito fica parada
    no Postgres. Um GET comum não espera nada — a trava só segura quem
    também pede a trava.

    O `populate_existing()` é a metade que não aparece no SQL. O
    SQLAlchemy guarda os objetos que já leu nesta sessão; se a conta já
    tinha sido lida antes (sem trava), a consulta travada devolveria o
    MESMO objeto, com o saldo ANTIGO — o SELECT esperou a outra
    transação terminar e o resultado novo seria jogado fora. Com o
    `populate_existing`, o objeto é regravado com o que o banco acabou
    de responder. Travar sem reler é esperar na fila pra decidir com o
    dado de antes da fila.
    """

    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def create(self, team: Team, plan: Plan, grace_until: date) -> Account:
        account = Account()

        account.account_key = str(uuid4())
        # A chave PIX aleatória da conta: a única porta de entrada de
        # dinheiro. É outro UUID, diferente da account_key, porque ela é
        # divulgada a patrocinadores — e a account_key não.
        account.pix_key = str(uuid4())
        account.team = team
        account.plan = plan
        account.balance = 0
        account.overdraft = 0
        account.grace_until = grace_until

        self.session.add(account)
        return account

    def update_plan(self, account: Account, plan: Plan) -> None:
        account.plan = plan

    def get_by_key(self, account_key: str) -> Account:
        return self.session.query(Account).filter(Account.account_key == account_key).first()

    def get_by_team(self, team_id: int) -> Account:
        return self.session.query(Account).filter(Account.team_id == team_id).first()

    def get_by_key_for_update(self, account_key: str) -> Account:
        return (
            self.session.query(Account)
            .filter(Account.account_key == account_key)
            .populate_existing()
            .with_for_update()
            .first()
        )

    def get_by_id_for_update(self, account_id: int) -> Account:
        return (
            self.session.query(Account)
            .filter(Account.id == account_id)
            .populate_existing()
            .with_for_update()
            .first()
        )

    def get_by_pix_key_for_update(self, pix_key: str) -> Account:
        return (
            self.session.query(Account)
            .filter(Account.pix_key == pix_key)
            .populate_existing()
            .with_for_update()
            .first()
        )

    def get_plan(self, enumerator: str) -> Plan:
        return self.session.query(Plan).filter(Plan.enumerator == enumerator).one()
