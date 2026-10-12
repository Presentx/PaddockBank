import re
from contextvars import ContextVar
from typing import Optional


# O cabeçalho em que o gateway entrega a identidade do usuário já
# autenticado: a `member_key` do responsável que está agindo.
MEMBER_KEY_HEADER = "X-Member-Key"

# Uma member_key é um UUID: 36 caracteres, hexadecimais e hífens. Valor
# fora desse formato não é identidade nenhuma, e é tratado como ausente
# — o mesmo cuidado do build_request_id em utils/request_context.py com
# texto que vem de fora.
SAFE_MEMBER_KEY = re.compile(r"[0-9a-fA-F-]{36}")


# Mesmo mecanismo do request_id (veja utils/request_context.py): um
# valor SEPARADO por requisição em andamento. Com uma variável comum,
# duas requisições simultâneas trocariam de identidade — e uma delas
# aprovaria um gasto em nome da outra.
#
# E mora em utils/ pelo mesmo motivo de lá: quem escreve é um
# middleware, quem lê é o controller, e utils/ é a pasta que as duas
# camadas podem importar sem fechar um ciclo.
_member_key: ContextVar[Optional[str]] = ContextVar("member_key", default=None)


def get_member_key() -> Optional[str]:
    """A member_key de quem está agindo nesta requisição, ou None."""
    return _member_key.get()


def set_member_key(received_member_key: Optional[str]) -> None:
    """Guarda a identidade desta requisição. Quem chama é o middleware.

    Sempre grava — inclusive None. Sem isso, uma requisição sem o
    cabeçalho poderia herdar a identidade deixada por outra.
    """
    if received_member_key is not None and SAFE_MEMBER_KEY.fullmatch(received_member_key):
        _member_key.set(received_member_key.lower())
        return

    _member_key.set(None)
