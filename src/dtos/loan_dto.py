from typing import List

from models import Loan


class LoanDTO:
    """O JSON do crédito.

    A taxa sai como `monthly_rate_bps`, em pontos-base e inteira (350 =
    3,5% ao mês), pelo mesmo motivo de o dinheiro sair em centavos:
    nenhum número desta API viaja como float.
    """

    @staticmethod
    def obj_to_dict(loan: Loan) -> dict:
        """O crédito INTEIRO, com as parcelas."""
        dto = LoanDTO.obj_to_simplified_dict(loan)
        dto["purpose"] = loan.purpose
        dto["requester_member_key"] = loan.requester.member_key
        dto["created_at"] = loan.created_at.isoformat()
        dto["installment_list"] = []

        for installment in loan.installment_list:
            installment_dto = dict()
            installment_dto["number"] = installment.number
            installment_dto["due_date"] = installment.due_date.isoformat()
            installment_dto["amount"] = installment.amount
            installment_dto["status"] = installment.status

            if installment.paid_at is None:
                installment_dto["paid_at"] = None
            else:
                installment_dto["paid_at"] = installment.paid_at.isoformat()

            dto["installment_list"].append(installment_dto)

        return dto

    @staticmethod
    def obj_to_simplified_dict(loan: Loan) -> dict:
        """O crédito sem as parcelas — o resumo que aparece dentro da conta."""
        dto = dict()
        dto["loan_key"] = loan.loan_key
        dto["status"] = loan.status
        dto["principal"] = loan.principal
        dto["monthly_rate_bps"] = loan.monthly_rate_bps
        dto["installments"] = loan.installments
        dto["installment_amount"] = loan.installment_amount

        return dto

    @staticmethod
    def list_obj_to_list_dict(loans_list: List[Loan]) -> List[dict]:
        loans_dict_list = []

        for loan in loans_list:
            loans_dict_list.append(LoanDTO.obj_to_simplified_dict(loan))

        return loans_dict_list

    @staticmethod
    def contracted_to_dict(loan: Loan, balance_after: int) -> dict:
        """A resposta da contratação: o crédito, as parcelas e o saldo já com o valor creditado."""
        dto = LoanDTO.obj_to_dict(loan)
        dto["balance_after"] = balance_after

        return dto
