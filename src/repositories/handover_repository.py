from uuid import uuid4

from database import Context
from models import Account, Handover, Member, Transaction


class HandoverRepository:
    """As consultas das passagens de gestão."""

    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def create(
        self,
        account: Account,
        outgoing_member: Member,
        incoming_member: Member,
        fee: int,
        transaction: Transaction,
        idempotency_key: str,
        request_id: str,
    ) -> Handover:
        handover = Handover()

        handover.handover_key = str(uuid4())
        handover.account_id = account.id
        handover.outgoing_member = outgoing_member
        handover.incoming_member = incoming_member
        handover.fee = fee
        handover.transaction = transaction
        handover.idempotency_key = idempotency_key
        handover.request_id = request_id

        self.session.add(handover)
        return handover

    def get_by_idempotency_key(self, account_id: int, idempotency_key: str) -> Handover:
        return (
            self.session.query(Handover)
            .filter(Handover.account_id == account_id, Handover.idempotency_key == idempotency_key)
            .first()
        )
