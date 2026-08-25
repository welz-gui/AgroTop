"""API FastAPI de Produção do AgroTop (Spec 0044 + Spec 0048 + Spec 0050 + Spec 0052).

Expõe autenticação JWT com refresh tokens revogáveis e endpoints essenciais de dados,
reaproveitando a camada de serviços e repositórios existente.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, Response, UploadFile, status
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
    CarenciaOutput,
    ConfirmarTratoInput,
    LoginInput,
    LogoutInput,
    LoteSummary,
    MedicamentoInput,
    MedicamentosOutput,
    MovimentarInput,
    MovimentarOutput,
    PesagemInput,
    PesagemOutput,
    PhotoSummary,
    PhotoUploadOutput,
    ProtocoloOutput,
    RefreshInput,
    RefreshOutput,
    TokenOutput,
    TratoPendenteOutput,
    UserSummary,
)
from database import (
    add_feeding_check,
    add_photo,
    get_all_lotes,
    get_pending_feedings,
    get_photo_image,
    get_photos,
)
from repositories.animais import get_all_animals, get_animal, move_animals_bulk
from repositories.pesagens import add_weighing, calculate_gmd
from repositories.sanidade import (
    add_medication,
    dose_for_animal,
    get_medications,
    get_protocols,
    get_withdrawal_end,
)
from services.zootecnia import calculate_gmd_total

MAX_PHOTO_SIZE = 5 * 1024 * 1024  # 5 MB
ALLOWED_PHOTO_MIMES = {"image/jpeg", "image/png", "image/jpg"}

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
    """Obtém detalhes do animal com métricas zootécnicas calculadas.

    Não filtra por status: um animal vendido/morto continua tendo ficha
    consultável (mesmo comportamento do `get_animal()` que o web usa) — só
    `GET /animais` (a listagem) filtra por status ativo por padrão.
    """
    item = get_animal(animal_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Animal não encontrado.",
        )

    gmd_recent = calculate_gmd(animal_id)
    gmd_total = calculate_gmd_total(item)

    return {
        "id": item["id"],
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


@app.get("/lotes", response_model=list[LoteSummary])
def list_lotes(
    _user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> list[dict[str, Any]]:
    """Lista piquetes/lotes cadastrados com capacidade e quantidade de animais ativos."""
    all_lotes = get_all_lotes()
    return [
        {
            "id": str(l["id"]),
            "nome": l.get("name") or "",
            "capacidade_ua": float(l["capacity_ua"]) if l.get("capacity_ua") is not None else None,
            "animais_ativos": int(l.get("animal_count") or 0),
        }
        for l in all_lotes
    ]


@app.post("/animais/movimentar", response_model=MovimentarOutput)
def movimentar_animais(
    data: MovimentarInput,
    user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> dict[str, list[str]]:
    """Transfere um ou mais animais para outro piquete (em lote)."""
    motivo = data.reason or "manejo"
    observacoes = data.notes or ""
    operador = user.get("username", "")

    resultado = move_animals_bulk(
        animal_ids=data.animal_ids,
        to_lote_id=data.to_lote_id,
        movement_date=data.movement_date,
        reason=motivo,
        operator=operador,
        notes=observacoes,
    )
    return resultado


@app.post("/animais/{animal_id}/fotos", response_model=PhotoUploadOutput, status_code=status.HTTP_201_CREATED)
def upload_animal_photo(
    animal_id: str,
    arquivo: UploadFile = File(...),
    taken_date: Optional[str] = Form(None),
    user: Annotated[dict[str, Any], Depends(get_current_user)] = None,
) -> dict[str, int]:
    """Envia uma foto do animal (JPEG ou PNG, até 5 MB)."""
    content_type = (arquivo.content_type or "").lower().strip()
    if content_type not in ALLOWED_PHOTO_MIMES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Tipo de arquivo não suportado. Aceitos: image/jpeg, image/png.",
        )

    content = arquivo.file.read()
    if len(content) > MAX_PHOTO_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE if hasattr(status, "HTTP_413_CONTENT_TOO_LARGE") else 413,
            detail="Arquivo excede o limite de 5 MB.",
        )

    mime = "image/jpeg" if content_type in ("image/jpeg", "image/jpg") else "image/png"
    operator = user.get("username", "") if user else ""

    try:
        add_photo(
            animal_id=animal_id,
            image_bytes=content,
            mime=mime,
            taken_date=taken_date,
            operator=operator,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    photos = get_photos(animal_id)
    if not photos:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erro ao recuperar foto salva.")

    return {"id": photos[0]["id"]}


@app.get("/animais/{animal_id}/fotos", response_model=list[PhotoSummary])
def list_animal_photos(
    animal_id: str,
    _user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> list[dict[str, Any]]:
    """Lista metadados das fotos do animal (sem os bytes da imagem)."""
    animal = get_animal(animal_id)
    if animal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Animal não encontrado.",
        )

    photos = get_photos(animal_id)
    return [
        {
            "id": p["id"],
            "taken_date": str(p["taken_date"]),
            "mime": p["mime"],
        }
        for p in photos
    ]


@app.get("/fotos/{photo_id}")
def get_photo_file(
    photo_id: int,
    _user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> Response:
    """Devolve a imagem binária da foto com Content-Type apropriado."""
    result = get_photo_image(photo_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Foto não encontrada.",
        )

    image_bytes, mime = result
    return Response(content=image_bytes, media_type=mime)


@app.get("/trato/pendentes", response_model=list[TratoPendenteOutput])
def list_tratos_pendentes(
    _user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> list[dict[str, Any]]:
    """Lista os itens de trato ativos e sua confirmação no período atual."""
    return [
        {
            "plano_id": plan["id"],
            "lote_id": str(plan["lote_id"]),
            "lote_nome": plan.get("lote_name") or "",
            "produto": plan["product_name"],
            "quantidade": float(plan["quantity"]),
            "unidade": plan["unit"],
            "frequencia": plan["frequency"],
            "insumo_id": plan.get("insumo_id"),
            "confirmado_no_periodo": plan["done_this_period"],
            "ultima_confirmacao": plan["last_check"],
        }
        for plan in get_pending_feedings(date.today())
    ]


@app.post("/trato/{plano_id}/confirmar", status_code=status.HTTP_201_CREATED)
def confirmar_trato(
    plano_id: int,
    data: ConfirmarTratoInput,
    user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> dict[str, bool]:
    """Confirma a execução de um item de trato ativo no dia de hoje."""
    today = date.today()
    plan = next(
        (item for item in get_pending_feedings(today) if item["id"] == plano_id),
        None,
    )
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item de trato não encontrado.",
        )

    add_feeding_check(
        plan_id=plano_id,
        lote_id=plan["lote_id"],
        check_date=today.isoformat(),
        status=data.situacao,
        actual_quantity=data.quantidade_aplicada,
        operator=user.get("username", ""),
        notes=data.notas or "",
        deduct_stock=data.baixar_estoque,
        insumo_id=plan.get("insumo_id"),
        quantity_unit=plan["unit"],
    )
    return {"ok": True}


@app.get("/protocolos", response_model=list[ProtocoloOutput])
def list_protocolos(
    _user: Annotated[dict[str, Any], Depends(get_current_user)],
    animal_id: Optional[str] = Query(
        None,
        description="Se informado, inclui dose_sugerida calculada para este animal "
                    "(services/sanidade.py::dose_for_animal — fixa ou proporcional ao "
                    "peso corrente, conforme o protocolo)",
    ),
) -> list[dict[str, Any]]:
    """Lista os protocolos sanitários ativos.

    Sem `animal_id`, `dose_sugerida` vem `null` em todos os itens — o cálculo depende
    do peso do animal (protocolos com `dose_ref_kg` são proporcionais ao peso, não uma
    dose fixa), então não há valor único a mostrar sem saber de quem.
    """
    animal = None
    if animal_id is not None:
        animal = get_animal(animal_id)
        if animal is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Animal não encontrado.",
            )

    return [
        {
            "id": protocolo["id"],
            "nome": protocolo["name"],
            "via": protocolo.get("route") or "",
            "carencia_dias": int(protocolo.get("withdrawal_days") or 0),
            "unidade_dose": protocolo.get("dose_unit") or "",
            "dose_sugerida": dose_for_animal(protocolo, animal) if animal is not None else None,
        }
        for protocolo in get_protocols(active_only=True)
    ]


@app.get("/animais/{animal_id}/medicamentos", response_model=MedicamentosOutput)
def list_medicamentos(
    animal_id: str,
    _user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> dict[str, Any]:
    """Lista aplicações e a maior data de carência ativa do animal."""
    carencia_ate = get_withdrawal_end(animal_id)
    aplicacoes = get_medications(animal_id)
    return {
        "carencia_ate": carencia_ate.isoformat() if carencia_ate is not None else None,
        "aplicacoes": [
            {
                "medicamento": aplicacao["medication_name"],
                "dose": float(aplicacao.get("dose") or 0),
                "unidade": aplicacao.get("unit") or "",
                "via": aplicacao.get("application_route") or "",
                "carencia_dias": int(aplicacao.get("withdrawal_days") or 0),
                "data": aplicacao["med_date"],
                "protocolo_id": aplicacao.get("protocol_id"),
            }
            for aplicacao in aplicacoes
        ],
    }


@app.post(
    "/animais/{animal_id}/medicamentos",
    response_model=CarenciaOutput,
    status_code=status.HTTP_201_CREATED,
)
def register_medicamento(
    animal_id: str,
    data: MedicamentoInput,
    user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> dict[str, Optional[str]]:
    """Registra uma aplicação individual sem movimentar estoque."""
    try:
        add_medication(
            animal_id=animal_id,
            medication_name=data.medicamento,
            dose=data.dose,
            unit=data.unidade,
            application_route=data.via,
            withdrawal_days=data.carencia_dias,
            med_date=data.data,
            applied_by=user.get("username", ""),
            insumo_id=None,
            notes=data.notas or "",
            protocol_id=data.protocolo_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    carencia_ate = get_withdrawal_end(animal_id)
    return {"carencia_ate": carencia_ate.isoformat() if carencia_ate is not None else None}
