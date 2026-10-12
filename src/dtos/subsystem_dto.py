from typing import List

from models import Subsystem


class SubsystemDTO:
    """O JSON do subsistema.

    `available` não é uma coluna: é o teto menos o comprometido,
    calculado aqui. Guardar os três no banco daria dois lugares pra
    mesma verdade.
    """

    @staticmethod
    def obj_to_dict(subsystem: Subsystem) -> dict:
        dto = dict()
        dto["subsystem_key"] = subsystem.subsystem_key
        dto["name"] = subsystem.name
        dto["owner_role_key"] = subsystem.owner_role.role_key
        dto["owner_role_name"] = subsystem.owner_role.name
        dto["budget"] = subsystem.budget
        dto["committed"] = subsystem.committed
        dto["available"] = subsystem.budget - subsystem.committed

        return dto

    @staticmethod
    def list_obj_to_list_dict(subsystems_list: List[Subsystem]) -> List[dict]:
        subsystems_dict_list = []

        for subsystem in subsystems_list:
            subsystems_dict_list.append(SubsystemDTO.obj_to_dict(subsystem))

        return subsystems_dict_list

    @staticmethod
    def only_obj_key(subsystem: Subsystem) -> dict:
        dto = dict()
        dto["subsystem_key"] = subsystem.subsystem_key

        return dto
