from typing import List

from models import Supplier


class SupplierDTO:
    """O JSON do fornecedor."""

    @staticmethod
    def obj_to_dict(supplier: Supplier) -> dict:
        dto = dict()
        dto["supplier_key"] = supplier.supplier_key
        dto["name"] = supplier.name
        dto["document_number"] = supplier.document_number
        dto["pix_key"] = supplier.pix_key

        return dto

    @staticmethod
    def list_obj_to_list_dict(suppliers_list: List[Supplier]) -> List[dict]:
        suppliers_dict_list = []

        for supplier in suppliers_list:
            suppliers_dict_list.append(SupplierDTO.obj_to_dict(supplier))

        return suppliers_dict_list

    @staticmethod
    def only_obj_key(supplier: Supplier) -> dict:
        dto = dict()
        dto["supplier_key"] = supplier.supplier_key

        return dto
