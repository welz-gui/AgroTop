"""Configurações da API Backend AgroTop."""

import os
from pathlib import Path

TOKEN_ALGORITHM = "HS256"
TOKEN_ISSUER = "agrotop-backend-api"
ACCESS_TOKEN_EXPIRE_SECONDS = 15 * 60  # 15 minutos (900 s)
REFRESH_TOKEN_EXPIRE_SECONDS = 7 * 24 * 60 * 60  # 7 dias (604800 s)


def get_secret_key() -> str:
    """Obtém a chave secreta da API (AGROTOP_API_SECRET ou .streamlit/secrets.toml).

    Exige no mínimo 32 caracteres para garantir segurança criptográfica (HMAC-SHA256).
    Se nenhuma chave válida for configurada, recusa-se a subir.
    """
    secret = os.environ.get("AGROTOP_API_SECRET", "").strip()
    if not secret:
        try:
            secrets_path = Path(".streamlit/secrets.toml")
            if secrets_path.exists():
                try:
                    import tomllib
                    with open(secrets_path, "rb") as f:
                        data = tomllib.load(f)
                except Exception:
                    import toml
                    data = toml.load(secrets_path)
                secret = (
                    data.get("api", {}).get("secret", "")
                    or data.get("api_secret", "")
                    or data.get("AGROTOP_API_SECRET", "")
                )
        except Exception:
            pass

    if len(secret) < 32:
        raise RuntimeError(
            "AGROTOP_API_SECRET deve ter pelo menos 32 caracteres. "
            "Defina a variável de ambiente AGROTOP_API_SECRET ou [api] secret em .streamlit/secrets.toml."
        )
    return secret
