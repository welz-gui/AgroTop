"""API mínima do AgroTop para validar o fluxo do aplicativo Flutter.

Execute sempre com ``AGROTOP_FORCE_SQLITE=1``. A PoC reutiliza autenticação,
repositórios e regras do projeto; ela não contém cópias de cálculos de negócio.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

import jwt
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict

from repositories.animais import get_all_animals, get_animal
from repositories.conexao import _conn, clear_cache
from repositories.pesagens import calculate_gmd
from services.seguranca import _hash, _is_legacy_hash, _verify_password
from services.zootecnia import calculate_gmd_total


TOKEN_ALGORITHM = "HS256"
TOKEN_ISSUER = "agrotop-poc-api"
TOKEN_TTL_HOURS = 8
_bearer = HTTPBearer(auto_error=False)


class LoginInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    username: str
    password: str


class TokenOutput(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict[str, Any]


def _secret() -> str:
    value = os.environ.get("AGROTOP_API_SECRET", "")
    if len(value) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AGROTOP_API_SECRET deve ter pelo menos 32 caracteres.",
        )
    return value


def _ensure_sqlite() -> None:
    forced = os.environ.get("AGROTOP_FORCE_SQLITE", "").strip().lower()
    if forced not in {"1", "true", "yes"}:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Esta PoC só inicia com AGROTOP_FORCE_SQLITE=1.",
        )


def _login(username: str, password: str) -> dict[str, Any] | None:
    """Valida ``users`` com o serviço PBKDF2 existente.

    Mantém também a migração transparente do hash SHA-256 legado, igual ao web.
    """
    with _conn() as con:
        row = con.execute(
            "SELECT id,username,password_hash,name,role FROM users WHERE username=?",
            (username,),
        ).fetchone()
    if not row or not _verify_password(password, row["password_hash"]):
        return None

    if _is_legacy_hash(row["password_hash"]):
        with _conn() as con:
            con.execute(
                "UPDATE users SET password_hash=? WHERE id=?",
                (_hash(password), row["id"]),
            )
        clear_cache()

    return {
        "id": row["id"],
        "username": row["username"],
        "name": row["name"],
        "role": row["role"],
    }


def _issue_token(user: dict[str, Any]) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(user["id"]),
        "username": user["username"],
        "name": user["name"],
        "role": user["role"],
        "iat": now,
        "exp": now + timedelta(hours=TOKEN_TTL_HOURS),
        "iss": TOKEN_ISSUER,
    }
    return jwt.encode(claims, _secret(), algorithm=TOKEN_ALGORITHM)


def _current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer)
    ],
) -> dict[str, Any]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token ausente.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        claims = jwt.decode(
            credentials.credentials,
            _secret(),
            algorithms=[TOKEN_ALGORITHM],
            issuer=TOKEN_ISSUER,
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return claims


def _animal_summary(animal: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": animal["id"],
        "breed": animal["breed"],
        "sex": animal["sex"],
        "current_weight": animal["current_weight"],
        "target_weight": animal["target_weight"],
        "lote_id": animal.get("lote_id"),
    }


app = FastAPI(
    title="AgroTop Mobile PoC API",
    version="0.1.0",
    description="Casca HTTP sobre os services e repositories existentes do AgroTop.",
)


@app.get("/health")
def health() -> dict[str, str]:
    _ensure_sqlite()
    return {"status": "ok", "database": "sqlite"}


@app.post("/auth/login", response_model=TokenOutput)
def login(data: LoginInput) -> TokenOutput:
    _ensure_sqlite()
    user = _login(data.username, data.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha inválidos.",
        )
    return TokenOutput(
        access_token=_issue_token(user),
        expires_in=TOKEN_TTL_HOURS * 60 * 60,
        user=user,
    )


@app.get("/animais")
def animais(_user: Annotated[dict[str, Any], Depends(_current_user)]) -> list[dict[str, Any]]:
    _ensure_sqlite()
    return [_animal_summary(animal) for animal in get_all_animals(status="ativo")]


@app.get("/animais/{animal_id}")
def animal(
    animal_id: str,
    _user: Annotated[dict[str, Any], Depends(_current_user)],
) -> dict[str, Any]:
    _ensure_sqlite()
    item = get_animal(animal_id)
    if item is None or item.get("status") != "ativo":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Animal não encontrado.")

    result = _animal_summary(item)
    result.update(
        {
            "birth_date": item.get("birth_date"),
            "entry_date": item.get("entry_date"),
            "entry_weight": item.get("entry_weight"),
            "lote_name": item.get("lote_name"),
            # As duas métricas são chamadas na camada Python existente. O app
            # apenas exibe estes campos; não há fórmula de GMD no Dart.
            "gmd_recent_kg_day": calculate_gmd(animal_id),
            "gmd_total_kg_day": calculate_gmd_total(item),
        }
    )
    return result
