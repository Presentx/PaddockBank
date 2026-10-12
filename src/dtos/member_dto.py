from typing import List

from models import Member


class MemberDTO:
    """O JSON do responsável.

    Na tabela o cargo e a situação são números apontando pra outras
    tabelas; na resposta, viram `role_key`, `role_name` e a palavra do
    status. Quem faz a travessia é este DTO.
    """

    @staticmethod
    def obj_to_dict(member: Member) -> dict:
        dto = dict()
        dto["member_key"] = member.member_key
        dto["name"] = member.name
        dto["document_number"] = member.document_number
        dto["email"] = member.email
        dto["phone"] = member.phone
        dto["pix_key"] = member.pix_key
        dto["role_key"] = member.role.role_key
        dto["role_name"] = member.role.name
        dto["is_finance"] = member.role.is_finance
        dto["status"] = member.status.enumerator

        return dto

    @staticmethod
    def obj_to_summary_dict(member: Member) -> dict:
        """Quem é, sem os dados de contato — pra aparecer DENTRO de outra resposta.

        O pedido de gasto diz quem solicitou e quem aprovou; a equipe
        diz quem é o financeiro. Nenhum dos dois precisa repetir CPF,
        telefone e chave PIX da pessoa.
        """
        dto = dict()
        dto["member_key"] = member.member_key
        dto["name"] = member.name
        dto["role_name"] = member.role.name

        return dto

    @staticmethod
    def list_obj_to_list_dict(members_list: List[Member]) -> List[dict]:
        members_dict_list = []

        for member in members_list:
            members_dict_list.append(MemberDTO.obj_to_dict(member))

        return members_dict_list

    @staticmethod
    def only_obj_key(member: Member) -> dict:
        dto = dict()
        dto["member_key"] = member.member_key

        return dto
