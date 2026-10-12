from typing import List

from models import Role


class RoleDTO:
    """Traduz o objeto do banco no JSON que a API devolve.

    O repository entrega um `Role` — o espelho da tabela, com o `id`
    numérico e o `parent_role_id`. Nada disso sai para o cliente: aqui
    o cargo superior vira `parent_role_key`, que é o único identificador
    que o mundo de fora conhece.

    Campo novo na resposta se acrescenta aqui — e só aqui.
    """

    @staticmethod
    def obj_to_dict(role: Role) -> dict:
        dto = dict()
        dto["role_key"] = role.role_key
        dto["name"] = role.name

        if role.parent is None:
            dto["parent_role_key"] = None
        else:
            dto["parent_role_key"] = role.parent.role_key

        dto["is_finance"] = role.is_finance

        return dto

    @staticmethod
    def list_obj_to_list_dict(roles_list: List[Role]) -> List[dict]:
        roles_dict_list = []

        for role in roles_list:
            roles_dict_list.append(RoleDTO.obj_to_dict(role))

        return roles_dict_list

    @staticmethod
    def only_obj_key(role: Role) -> dict:
        dto = dict()
        dto["role_key"] = role.role_key

        return dto
