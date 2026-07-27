from fastapi import APIRouter, Depends
from schemas.schemas import SimulacaoTerminacaoRequest, SimulacaoTerminacaoResponse
from services.terminacao_service import processar_simulacao_terminacao
from dependencies import get_current_user

router = APIRouter(prefix="/simular-terminacao", tags=["Simulador de Terminação"])

@router.post("", response_model=SimulacaoTerminacaoResponse, summary="Simular estratégias de terminação de gado")
async def simular_terminacao_endpoint(
    req: SimulacaoTerminacaoRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Calcula e compara o desempenho financeiro entre estratégias de terminação:
    - Pasto Adubado
    - Semiconfinamento
    - Confinamento
    
    Retorna o número de dias necessários, ganho total de arrobas, custo alimentar,
    lucro por dia e identifica a estratégia mais rentável.
    """
    return processar_simulacao_terminacao(req)
