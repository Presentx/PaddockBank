from typing import List

from models import Transaction


class TransactionDTO:
    """O JSON de uma linha do extrato."""

    @staticmethod
    def obj_to_dict(transaction: Transaction) -> dict:
        """A linha como o extrato a mostra.

        `amount` sai com sinal (crédito positivo, débito negativo) e
        `balance_after` é o saldo logo depois da linha. O `request_id`
        vai junto: é com ele que se acha, no log, a requisição que
        causou o lançamento.
        """
        dto = dict()
        dto["transaction_key"] = transaction.transaction_key
        dto["type"] = transaction.type.enumerator
        dto["amount"] = transaction.amount
        dto["balance_after"] = transaction.balance_after

        if transaction.subsystem is None:
            dto["subsystem_key"] = None
        else:
            dto["subsystem_key"] = transaction.subsystem.subsystem_key

        dto["counterparty_name"] = transaction.counterparty_name
        dto["counterparty_document"] = transaction.counterparty_document
        dto["description"] = transaction.description
        dto["request_id"] = transaction.request_id
        dto["created_at"] = transaction.created_at.isoformat()

        return dto

    @staticmethod
    def list_obj_to_list_dict(transactions_list: List[Transaction]) -> List[dict]:
        transactions_dict_list = []

        for transaction in transactions_list:
            transactions_dict_list.append(TransactionDTO.obj_to_dict(transaction))

        return transactions_dict_list

    @staticmethod
    def receipt_to_dict(transaction: Transaction) -> dict:
        """O comprovante de um depósito: a chave da linha e o saldo resultante."""
        dto = dict()
        dto["transaction_key"] = transaction.transaction_key
        dto["balance_after"] = transaction.balance_after

        return dto
