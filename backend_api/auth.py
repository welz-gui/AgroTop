"""Autenticação, JWT e controle de refresh tokens para a API Backend."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend_api.config import (
    ACCESS_TOKEN_EXPIRE_SECONDS,
    REFRESH_TOKEN_EXPIRE_SECONDS,
    TOKEN_ALGORITHM,
    TOKEN_ISSUER,
    get_secret_key,
)
from repositories.conexao import _conn, clear_cache
from services.seguranca import _hash, _is_legacy_hash, _verify_password

bearer_scheme = HTTPBearer(auto_error=False)


def authenticate_user(username: str, password: str) -> dict[str, Any] | None:
    """Valida as credenciais do usuário usando PBKDF2/SHA-256 e efetua migração transparente."""
    with _conn() as con:
        row = con.execute(
            "SELECT id, username, password_hash, name, role FROM users WHERE username = ?",
            (username,),
        ).fetchone()

    if not row or not _verify_password(password, row["password_hash"]):
        return None

    # Migração automática de hash legado
    if _is_legacy_hash(row["password_hash"]):
        try:
            with _conn() as con:
                con.execute(
                    "UPDATE users SET password_hash = ? WHERE id = ?",
                    (_hash(password), row["id"]),
                )
            clear_cache()
        except Exception:
            pass

    return {
        "id": row["id"],
        "username": row["username"],
        "name": row["name"],
        "role": row["role"],
    }


def create_access_token(user: dict[str, Any]) -> str:
    """Gera um JWT de curta duração (15 min) para o usuário."""
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(user["id"]),
        "username": user["username"],
        "name": user["name"],
        "role": user["role"],
        "iat": now,
        "exp": now + timedelta(seconds=ACCESS_TOKEN_EXPIRE_SECONDS),
        "iss": TOKEN_ISSUER,
        "type": "access",
    }
    return jwt.encode(claims, get_secret_key(), algorithm=TOKEN_ALGORITHM)


def create_refresh_token(user_id: int) -> str:
    """Gera um token de refresh revogável (7 dias) e persiste no banco de dados."""
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expires_at = (now + timedelta(seconds=REFRESH_TOKEN_EXPIRE_SECONDS)).isoformat()
    created_at = now.isoformat()

    with _conn() as con:
        con.execute(
            "INSERT INTO api_refresh_tokens (token, user_id, expires_at, revoked, created_at) "
            "VALUES (?, ?, ?, 0, ?)",
            (token, user_id, expires_at, created_at),
        )

    return token


def verify_refresh_token(token: str) -> dict[str, Any]:
    """Valida o refresh token no banco de dados e retorna os dados do usuário associado."""
    with _conn() as con:
        row = con.execute(
            "SELECT token, user_id, expires_at, revoked FROM api_refresh_tokens WHERE token = ?",
            (token,),
        ).fetchone()

    if not row or int(row["revoked"]) != 0:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido ou expirado.",
        )

    try:
        exp_dt = datetime.fromisoformat(row["expires_at"])
        if exp_dt.tzinfo is None:
            exp_dt = exp_dt.replace(tzinfo=timezone.utc)
        if exp_dt <= datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token inválido ou expirado.",
            )
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido ou expirado.",
        ) from exc

    with _conn() as con:
        user_row = con.execute(
            "SELECT id, username, name, role FROM users WHERE id = ?",
            (row["user_id"],),
        ).fetchone()

    if not user_row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado.",
        )

    return {
        "id": user_row["id"],
        "username": user_row["username"],
        "name": user_row["name"],
        "role": user_row["role"],
    }


def revoke_refresh_token(token: str) -> None:
    """Revoga o refresh token fornecido no banco de dados."""
    with _conn() as con:
        con.execute(
            "UPDATE api_refresh_tokens SET revoked = 1 WHERE token = ?",
            (token,),
        )


def get_current_user(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(bearer_scheme)],
) -> dict[str, Any]:
    """Dependency para proteger rotas: decodifica e valida o JWT Bearer token."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token ausente.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        claims = jwt.decode(
            credentials.credentials,
            get_secret_key(),
            algorithms=[TOKEN_ALGORITHM],
            issuer=TOKEN_ISSUER,
        )
        if claims.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido ou expirado.",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    return claims
