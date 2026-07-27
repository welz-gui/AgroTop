from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from config import settings

security = HTTPBearer(auto_error=False)

async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> dict:
    """
    Valida o token Bearer JWT enviado pelo App Flutter vindo do Supabase Auth.
    Se o SUPABASE_JWT_SECRET estiver configurado, decodifica a assinatura.
    Caso contrário em dev, extrai as alegações do payload JWT.
    """
    if not credentials:
        # Se não enviou token, aceita como anônimo em desenvolvimento ou levanta 401
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de autenticação não fornecido.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    try:
        if settings.SUPABASE_JWT_SECRET:
            payload = jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                options={"verify_aud": False}
            )
        else:
            # Em modo dev sem secret, extrai payload não verificado
            payload = jwt.get_unverified_claims(token)
            
        user_id: str = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token de autenticação inválido (subject ausente).",
            )
        return {
            "id": user_id,
            "email": payload.get("email"),
            "role": payload.get("role", "authenticated"),
            "user_metadata": payload.get("user_metadata", {})
        }
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Falha na validação do token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
