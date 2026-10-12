from models import Handover


class HandoverDTO:
    """O JSON da passagem de gestão."""

    @staticmethod
    def obj_to_dict(handover: Handover, balance_after: int) -> dict:
        """Quem assumiu, quanto foi cobrado e o saldo que ficou.

        O `balance_after` chega pronto do controller: quando houve
        tarifa, é o saldo gravado na linha HANDOVER_FEE do extrato;
        quando a passagem foi isenta, não existe linha, e a passagem
        não mexeu no saldo.
        """
        dto = dict()
        dto["handover_key"] = handover.handover_key
        dto["finance_member_key"] = handover.incoming_member.member_key
        dto["fee"] = handover.fee
        dto["balance_after"] = balance_after

        return dto
