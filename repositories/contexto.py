"""De onde vem a escrita em curso: a origem e o aparelho (PNIB §6.2 e §14.1).

O web grava direto pelos repositórios e não define nada aqui: vale o padrão, `web` e sem aparelho.
A API define, por requisição, `app` e o aparelho que o cliente declarou (`backend_api/main.py`).
`eventos._gravar` e `eventos.auditar_em` leem este contexto quando o chamador não passa a origem
ou o aparelho, e é por isso que os mais de uma dezena de lugares que gravam evento (pesagem,
aplicação, movimentação, estorno, correção...) não precisam repassar nada.

É uma `ContextVar`, não uma global: cada requisição tem a sua cópia, e o `restaurar` a devolve ao
estado anterior ao fim dela, então nada passa de uma requisição para a seguinte.
"""

from contextvars import ContextVar, Token
from typing import Optional

ORIGEM_PADRAO = "web"

_origem: ContextVar[str] = ContextVar("agrotop_origem", default=ORIGEM_PADRAO)
_dispositivo: ContextVar[Optional[str]] = ContextVar("agrotop_dispositivo", default=None)


def origem_atual() -> str:
    return _origem.get()


def dispositivo_atual() -> Optional[str]:
    return _dispositivo.get()


def definir(origem: str, dispositivo: Optional[str] = None) -> tuple[Token, Token]:
    """Define a origem e o aparelho da requisição em curso. Devolve o que `restaurar` precisa."""
    return _origem.set(origem), _dispositivo.set(dispositivo)


def restaurar(tokens: tuple[Token, Token]) -> None:
    _origem.reset(tokens[0])
    _dispositivo.reset(tokens[1])
