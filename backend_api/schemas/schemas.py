from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

# --- Schemas do Simulador de Terminação ---
class TerminacaoCenario(BaseModel):
    nome: str = Field(..., example="Semiconfinamento")
    gmd: float = Field(..., description="Ganho Médio Diário em kg/dia", example=1.1)
    custo_dia: float = Field(..., description="Custo alimentar por dia em R$", example=8.50)
    rendimento: float = Field(default=0.54, description="Rendimento de carcaça (ex: 0.54 para 54%)", example=0.54)

class SimulacaoTerminacaoRequest(BaseModel):
    peso_atual: float = Field(..., description="Peso inicial do animal em kg", example=380.0)
    peso_meta: float = Field(..., description="Peso meta de abate em kg", example=540.0)
    preco_arroba: float = Field(..., description="Preço da @ em R$", example=230.0)
    custo_boi_magro: float = Field(default=0.0, description="Custo de aquisição do animal em R$", example=0.0)
    cenarios: Optional[List[TerminacaoCenario]] = None

class ResultadoCenario(BaseModel):
    nome: str
    dias: int
    arrobas_produzidas: float
    custo_alimentar: float
    custo_por_arroba: float
    receita: float
    lucro: float
    lucro_por_dia: float
    margem_pct: float
    viavel: bool

class SimulacaoTerminacaoResponse(BaseModel):
    peso_atual: float
    peso_meta: float
    preco_arroba: float
    ganho_necessario_kg: float
    melhor_estratégia: Optional[str]
    cenarios: List[ResultadoCenario]

# --- Schemas de Tarefas Assíncronas & Processamento de Imagens ---
class TaskStatusResponse(BaseModel):
    task_id: str
    status: str = Field(..., description="pending, processing, completed, failed")
    progress_pct: int = Field(default=0, ge=0, le=100)
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class ImageOCRResult(BaseModel):
    brinco_detectado: Optional[str] = None
    qr_code: Optional[str] = None
    confianca: float = 0.0
    foto_url: Optional[str] = None

# --- Schemas do Dashboard ---
class DashboardStatsResponse(BaseModel):
    total_animais_ativos: int
    peso_medio_kg: float
    gmd_medio_rebanho: float
    total_lotes: int
    alertas_carência: int
    alertas_desempenho_baixo: int
