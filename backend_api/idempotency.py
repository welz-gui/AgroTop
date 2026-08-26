"""Módulo de controle de idempotência para endpoints de escrita da API Backend (Spec 0059 / ADR 0006).

Armazena e recupera respostas de requisições HTTP idempotentes para evitar duplicações.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from repositories.conexao import _conn


def get_cached_response(key: str) -> Optional[dict[str, Any]]:
    """None se a chave não foi vista. Senão, {"status_code": int, "response_body": <dict decodificado>}."""
    if not key:
        return None

    with _conn() as con:
        row = con.execute(
            "SELECT status_code, response_body FROM api_idempotency_keys WHERE idempotency_key = ?",
            (key,),
        ).fetchone()

    if not row:
        return None

    try:
        body = json.loads(row["response_body"])
    except (json.JSONDecodeError, TypeError):
        body = row["response_body"]

    return {
        "status_code": int(row["status_code"]),
        "response_body": body,
    }


def store_response(key: str, endpoint: str, status_code: int, response_body: dict | Any) -> None:
    """Grava a chave. Chame só depois de confirmar que a escrita deu certo."""
    if not key:
        return

    body_str = json.dumps(response_body)

    with _conn() as con:
        con.execute(
            "INSERT INTO api_idempotency_keys (idempotency_key, endpoint, status_code, response_body) "
            "VALUES (?, ?, ?, ?)",
            (key, endpoint, status_code, body_str),
        )
