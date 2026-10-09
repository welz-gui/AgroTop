"""Módulo de controle de idempotência para endpoints de escrita da API Backend (Spec 0059 / ADR 0006).

Armazena e recupera respostas de requisições HTTP idempotentes para evitar duplicações.

Fluxo atômico (`executar_idempotente`): a chave é RESERVADA antes da escrita, com o
hash do pedido, e só depois recebe a resposta final. Duas requisições simultâneas com
a mesma chave não passam juntas — a segunda vê a reserva e recebe 409. Reutilizar a
chave com outro conteúdo é erro do cliente (422), não resposta antiga.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

from fastapi import HTTPException, Response, status

from repositories.conexao import _conn

# Reserva 'em_andamento' mais velha que isso foi abandonada (processo caiu entre a
# reserva e a resposta) e pode ser retomada por outra tentativa.
PRAZO_RESERVA = timedelta(minutes=5)

_EM_ANDAMENTO = "em_andamento"
_CONCLUIDA = "concluida"


class ChaveReutilizada(Exception):
    """A mesma Idempotency-Key chegou com conteúdo diferente do original."""


class RequisicaoEmAndamento(Exception):
    """A chave está reservada por outra requisição que ainda não terminou."""


def hash_requisicao(endpoint: str, payload: Any) -> str:
    """SHA-256 de endpoint + corpo, estável entre ordens de chave do JSON."""
    canonico = json.dumps(
        {"endpoint": endpoint, "payload": payload},
        sort_keys=True,
        ensure_ascii=False,
        default=str,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _resposta(row) -> dict[str, Any]:
    try:
        body = json.loads(row["response_body"])
    except (json.JSONDecodeError, TypeError):
        body = row["response_body"]

    return {
        "status_code": int(row["status_code"]),
        "response_body": body,
    }


def get_cached_response(key: str) -> Optional[dict[str, Any]]:
    """None se a chave não foi vista (ou ainda está em andamento). Senão, {"status_code": int, "response_body": <dict decodificado>}."""
    if not key:
        return None

    with _conn() as con:
        row = con.execute(
            "SELECT status_code, response_body FROM api_idempotency_keys "
            "WHERE idempotency_key = ? AND estado = ?",
            (key, _CONCLUIDA),
        ).fetchone()

    if not row:
        return None

    return _resposta(row)


def store_response(key: str, endpoint: str, status_code: int, response_body: dict | Any) -> None:
    """Grava a chave já concluída, sem reserva prévia. Chame só depois de confirmar que a escrita deu certo.

    Os endpoints usam `executar_idempotente`; isto fica para quem não precisa de reserva.
    """
    if not key:
        return

    body_str = json.dumps(response_body)

    with _conn() as con:
        con.execute(
            "INSERT INTO api_idempotency_keys (idempotency_key, endpoint, status_code, response_body) "
            "VALUES (?, ?, ?, ?)",
            (key, endpoint, status_code, body_str),
        )


def reservar(key: str, endpoint: str, request_hash: str) -> Optional[dict[str, Any]]:
    """Reserva a chave de forma atômica.

    Devolve None quando a reserva é nossa (pode escrever) ou a resposta guardada
    quando a chave já foi concluída com o mesmo pedido.
    Levanta `ChaveReutilizada` (conteúdo diferente) ou `RequisicaoEmAndamento`.
    """
    for _ in range(3):
        agora = _agora()
        with _conn() as con:
            cur = con.execute(
                "INSERT INTO api_idempotency_keys "
                "(idempotency_key, endpoint, status_code, response_body, request_hash, estado, reservada_em) "
                "VALUES (?, ?, 0, '', ?, ?, ?) ON CONFLICT (idempotency_key) DO NOTHING",
                (key, endpoint, request_hash, _EM_ANDAMENTO, agora.isoformat()),
            )
            if cur.rowcount == 1:
                return None

            row = con.execute(
                "SELECT status_code, response_body, request_hash, estado, reservada_em "
                "FROM api_idempotency_keys WHERE idempotency_key = ?",
                (key,),
            ).fetchone()
            if row is None:
                # Liberada entre o INSERT e o SELECT: tenta reservar de novo.
                continue

            guardado = row["request_hash"]
            if guardado is not None and guardado != request_hash:
                raise ChaveReutilizada(key)

            if row["estado"] == _CONCLUIDA:
                return _resposta(row)

            if _reserva_vencida(row["reservada_em"], agora):
                # Retoma a reserva abandonada; o UPDATE condicionado ao valor antigo
                # garante que só uma das tentativas concorrentes fica com ela.
                cur = con.execute(
                    "UPDATE api_idempotency_keys SET reservada_em = ?, request_hash = ? "
                    "WHERE idempotency_key = ? AND estado = ? AND COALESCE(reservada_em, '') = ?",
                    (agora.isoformat(), request_hash, key, _EM_ANDAMENTO, row["reservada_em"] or ""),
                )
                if cur.rowcount == 1:
                    return None

            raise RequisicaoEmAndamento(key)

    raise RequisicaoEmAndamento(key)


def _reserva_vencida(reservada_em: Optional[str], agora: datetime) -> bool:
    if not reservada_em:
        return True
    try:
        desde = datetime.fromisoformat(reservada_em)
    except ValueError:
        return True
    if desde.tzinfo is None:
        desde = desde.replace(tzinfo=timezone.utc)
    return agora - desde > PRAZO_RESERVA


def concluir(key: str, status_code: int, response_body: dict | Any) -> None:
    """Fecha a reserva com a resposta final."""
    with _conn() as con:
        con.execute(
            "UPDATE api_idempotency_keys SET status_code = ?, response_body = ?, estado = ? "
            "WHERE idempotency_key = ?",
            (status_code, json.dumps(response_body), _CONCLUIDA, key),
        )


def liberar(key: str) -> None:
    """Desfaz a reserva quando a escrita falhou, para o cliente poder tentar de novo."""
    with _conn() as con:
        con.execute(
            "DELETE FROM api_idempotency_keys WHERE idempotency_key = ? AND estado = ?",
            (key, _EM_ANDAMENTO),
        )


def executar_idempotente(
    key: Optional[str],
    endpoint: str,
    payload: Any,
    response: Response,
    status_code: int,
    executar: Callable[[], Any],
) -> Any:
    """Roda `executar` uma única vez por Idempotency-Key.

    Sem chave, só executa. Com chave: reserva → executa → guarda a resposta. Se
    `executar` levantar, a reserva é desfeita e a exceção segue (erro não é cacheado).
    """
    if not key:
        return executar()

    try:
        cached = reservar(key, endpoint, hash_requisicao(endpoint, payload))
    except ChaveReutilizada:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Idempotency-Key já foi usada com outro conteúdo. Gere uma chave nova para um novo registro.",
        )
    except RequisicaoEmAndamento:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Requisição com esta Idempotency-Key ainda está em processamento.",
        )

    if cached is not None:
        response.status_code = cached["status_code"]
        return cached["response_body"]

    try:
        out = executar()
    except BaseException:
        try:
            liberar(key)
        except Exception:
            # A exceção original é a que importa; a reserva vencida se retoma sozinha.
            pass
        raise

    concluir(key, status_code, out)
    return out
