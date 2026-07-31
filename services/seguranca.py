"""Hashing e verificação de senha (PBKDF2-SHA256 + salt).

Aceita o formato legado SHA-256 para permitir a migração no login.
Sem SQL e sem Streamlit.
"""

import hashlib

# Custo do PBKDF2. Aumentar é seguro (hashes antigos guardam o próprio número de
# iterações no formato e continuam verificáveis); diminuir enfraquece as senhas.
_PBKDF2_ITERATIONS = 260_000


def _hash(pwd: str) -> str:
    """Gera hash de senha com PBKDF2-SHA256 + salt aleatório.
    Formato: pbkdf2_sha256$<iteracoes>$<salt_hex>$<hash_hex>."""
    import secrets
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", pwd.encode(), salt, _PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt.hex()}${dk.hex()}"


def _is_legacy_hash(stored: str) -> bool:
    """True se o hash está no formato antigo (SHA-256 sem salt)."""
    return not (stored or "").startswith("pbkdf2_sha256$")


def _verify_password(pwd: str, stored: str) -> bool:
    """Verifica a senha contra o hash armazenado (PBKDF2 novo ou SHA-256 legado)."""
    import hmac
    if not stored:
        return False
    if stored.startswith("pbkdf2_sha256$"):
        try:
            _, iters, salt_hex, dk_hex = stored.split("$")
            dk = hashlib.pbkdf2_hmac("sha256", pwd.encode(),
                                     bytes.fromhex(salt_hex), int(iters))
            return hmac.compare_digest(dk.hex(), dk_hex)
        except (ValueError, TypeError):
            return False
    # Legado: SHA-256 sem salt
    legacy = hashlib.sha256(pwd.encode()).hexdigest()
    return hmac.compare_digest(legacy, stored)
