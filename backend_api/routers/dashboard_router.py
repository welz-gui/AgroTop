from fastapi import APIRouter, Depends
from schemas.schemas import DashboardStatsResponse
from dependencies import get_current_user

router = APIRouter(prefix="/dashboard", tags=["Dashboard & Estatísticas"])

@router.get("/stats", response_model=DashboardStatsResponse, summary="Obter resumo geral do rebanho para a Home mobile")
async def get_dashboard_stats(current_user: dict = Depends(get_current_user)):
    """
    Retorna indicadores agregados do rebanho para exibição no aplicativo mobile:
    - Total de animais ativos
    - Peso médio do rebanho
    - GMD médio
    - Alertas de carência sanitária
    - Alertas de animais com baixo ganho de peso
    """
    # Exemplo de resposta rápida estruturada
    return DashboardStatsResponse(
        total_animais_ativos=185,
        peso_medio_kg=412.5,
        gmd_medio_rebanho=0.850,
        total_lotes=8,
        alertas_carência=2,
        alertas_desempenho_baixo=5
    )
