"""API FastAPI de Produção do AgroTop (Spec 0044).

Expõe autenticação JWT com refresh tokens revogáveis e endpoints essenciais de dados,
reaproveitando a camada de serviços e repositórios existente.
"""

from __future__ import annotations

from typing import Annotated, Any, Optional, Union

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from backend_api.auth import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    get_current_user,
    revoke_refresh_token,
    verify_refresh_token,
)
from backend_api.config import ACCESS_TOKEN_EXPIRE_SECONDS
from backend_api.schemas import (
    AnimalDetail,
    AnimalSummary,
    LoginInput,
    LogoutInput,
    PesagemInput,
    PesagemOutput,
    RefreshInput,
    RefreshOutput,
    TokenOutput,
    UserSummary,
)
from repositories.animais import get_all_animals, get_animal
from repositories.pesagens import add_weighing, calculate_gmd
from services.zootecnia import calculate_gmd_total

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="AgroTop API de Produção",
    version="1.0.0",
    description="API RESTful para integração com aplicativos mobile e serviços externos.",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": "AgroTop Backend API"}


@app.post("/auth/login", response_model=TokenOutput)
@limiter.limit("5/5minutes")
def login(request: Request, data: LoginInput) -> TokenOutput:
    """Autentica usuário e retorna access_token JWT (15 min) e refresh_token (7 dias)."""
    user = authenticate_user(data.username, data.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha inválidos.",
        )

    access_token = create_access_token(user)
    refresh_token = create_refresh_token(user["id"])

    return TokenOutput(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_SECONDS,
        refresh_token=refresh_token,
        user=UserSummary(
            id=user["id"],
            username=user["username"],
            name=user["name"],
            role=user["role"],
        ),
    )


@app.post("/auth/refresh", response_model=RefreshOutput)
def refresh(data: RefreshInput) -> RefreshOutput:
    """Emite um novo access_token usando um refresh token válido e não revogado."""
    user = verify_refresh_token(data.refresh_token)
    new_access_token = create_access_token(user)
    return RefreshOutput(
        access_token=new_access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_SECONDS,
    )


@app.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(data: LogoutInput) -> Response:
    """Revoga o refresh token fornecido."""
    revoke_refresh_token(data.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/animais", response_model=list[AnimalSummary])
def list_animais(
    _user: Annotated[dict[str, Any], Depends(get_current_user)],
    skip: int = Query(0, ge=0, description="Número de registros a pular"),
    limit: int = Query(50, ge=1, le=500, description="Número máximo de registros"),
    status_filter: Optional[str] = Query("ativo", alias="status", description="Filtro de status do animal"),
) -> list[dict[str, Any]]:
    """Lista animais cadastrados com paginação."""
    all_animals = get_all_animals(status=status_filter)
    paginated = all_animals[skip : skip + limit]

    return [
        {
            "id": a["id"],
            "tag": a.get("tag") or a.get("id"),
            "name": a.get("name"),
            "breed": a.get("breed"),
            "sex": a.get("sex"),
            "birth_date": a.get("birth_date"),
            "entry_weight": a.get("entry_weight"),
            "current_weight": a.get("current_weight"),
            "target_weight": a.get("target_weight"),
            "status": a.get("status"),
            "lote_id": a.get("lote_id"),
            "lot_name": a.get("lote_name"),
            "animal_uuid": a.get("uuid") or a.get("animal_uuid"),
        }
        for a in paginated
    ]


@app.get("/animais/{animal_id}", response_model=AnimalDetail)
def get_animal_detail(
    animal_id: str,
    _user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> dict[str, Any]:
    """Obtém detalhes do animal com métricas zootécnicas calculadas."""
    item = get_animal(animal_id)
    if item is None or item.get("status") != "ativo":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Animal não encontrado.",
        )

    gmd_recent = calculate_gmd(animal_id)
    gmd_total = calculate_gmd_total(item)

    return {
        "id": item["id"],
        "tag": item.get("tag") or item.get("id"),
        "name": item.get("name"),
        "breed": item.get("breed"),
        "sex": item.get("sex"),
        "birth_date": item.get("birth_date"),
        "entry_date": item.get("entry_date"),
        "entry_weight": item.get("entry_weight"),
        "current_weight": item.get("current_weight"),
        "target_weight": item.get("target_weight"),
        "status": item.get("status"),
        "lote_id": item.get("lote_id"),
        "lot_name": item.get("lote_name"),
        "fornecedor_id": item.get("fornecedor_id"),
        "fornecedor_name": item.get("fornecedor_name"),
        "animal_uuid": item.get("uuid") or item.get("animal_uuid"),
        "gmd_recent_kg_day": gmd_recent,
        "gmd_total_kg_day": gmd_total,
    }


@app.post("/animais/{animal_id}/pesagens", response_model=PesagemOutput, status_code=status.HTTP_201_CREATED)
def register_pesagem(
    animal_id: str,
    data: PesagemInput,
    user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> PesagemOutput:
    """Registra uma nova pesagem para o animal autenticado pelo operador."""
    try:
        add_weighing(
            animal_id=animal_id,
            weight=data.peso,
            weigh_date=data.data,
            operator=user.get("username", ""),
            method=data.method,
            notes=data.notes,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    return PesagemOutput(
        status="success",
        message="Pesagem registrada com sucesso.",
        animal_id=animal_id,
        peso=data.peso,
        data=data.data,
    )
