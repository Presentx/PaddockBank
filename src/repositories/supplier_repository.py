from uuid import uuid4

from database import Context
from models import Supplier, Team


class SupplierRepository:
    """As consultas dos fornecedores."""

    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def create(self, team: Team, supplier_data: dict) -> Supplier:
        supplier = Supplier()

        supplier.supplier_key = str(uuid4())
        supplier.team_id = team.id
        supplier.name = supplier_data["name"]
        supplier.document_number = supplier_data["document_number"]
        supplier.pix_key = supplier_data["pix_key"]

        self.session.add(supplier)
        return supplier

    def get_by_key(self, supplier_key: str) -> Supplier:
        return self.session.query(Supplier).filter(Supplier.supplier_key == supplier_key).first()

    def get_by_document_number(self, team_id: int, document_number: str) -> Supplier:
        return (
            self.session.query(Supplier)
            .filter(Supplier.team_id == team_id, Supplier.document_number == document_number)
            .first()
        )

    def list_page(self, team_id: int, limit: int, offset: int) -> list:
        query = (
            self.session.query(Supplier)
            .filter(Supplier.team_id == team_id)
            .order_by(Supplier.created_at.desc(), Supplier.id.desc())
        )

        return query.limit(limit + 1).offset(offset).all()
