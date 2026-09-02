"""Modelos Pydantic (schemas) da API Backend AgroTop."""

from dataclasses import dataclass
from typing import Literal, Optional, Union
from fastapi import File, Form, UploadFile
from pydantic import BaseModel, ConfigDict, Field


class LoginInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    username: str = Field(..., min_length=1, description="Nome de usuário")
    password: str = Field(..., min_length=1, description="Senha")


class UserSummary(BaseModel):
    id: int
    username: str
    name: str
    role: str


class TokenOutput(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str
    user: UserSummary


class RefreshInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    refresh_token: str = Field(..., min_length=1, description="Refresh token para renovação")


class RefreshOutput(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class LogoutInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    refresh_token: str = Field(..., min_length=1, description="Refresh token a revogar")


class AnimalSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    # `animals` não tem coluna `tag` nem `name` (o brinco já É o `id`) — não
    # exponha campo que sempre vem nulo, é contrato enganoso pra quem
    # implementar o mobile depois.
    id: Union[str, int]
    breed: Optional[str] = None
    sex: Optional[str] = None
    birth_date: Optional[str] = None
    entry_weight: Optional[float] = None
    current_weight: Optional[float] = None
    target_weight: Optional[float] = None
    status: Optional[str] = None
    lote_id: Optional[Union[str, int]] = None
    lot_name: Optional[str] = None
    animal_uuid: Optional[str] = None


class AnimalDetail(AnimalSummary):
    entry_date: Optional[str] = None
    fornecedor_id: Optional[int] = None
    fornecedor_name: Optional[str] = None
    gmd_recent_kg_day: Optional[float] = None
    gmd_total_kg_day: Optional[float] = None


class PesagemInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    peso: float = Field(..., gt=0, description="Peso em quilogramas (deve ser > 0)")
    data: str = Field(..., description="Data da pesagem no formato YYYY-MM-DD")
    method: str = Field(default="pesado", description="Método da pesagem (ex: pesado, estimado, fita)")
    notes: str = Field(default="", description="Observações opcionais")


class PesagemOutput(BaseModel):
    status: str = "success"
    message: str
    animal_id: Union[str, int]
    peso: float
    data: str


class LoteSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    nome: str
    capacidade_ua: Optional[float] = None
    animais_ativos: int


class CriarLoteInput(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    id: str = Field(..., min_length=1, description="Identificador do lote/piquete (ex: P07)")
    nome: str = Field(..., min_length=1, description="Nome do piquete/lote")
    area_ha: float = Field(..., ge=0, description="Área em hectares (>= 0)")
    capacidade_ua: float = Field(..., ge=0, description="Capacidade em UA (>= 0)")
    observacoes: str = Field(default="", description="Observações opcionais")



class MovimentarInput(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    animal_ids: list[str] = Field(..., min_length=1, description="Lista de IDs dos animais a movimentar")
    to_lote_id: str = Field(..., min_length=1, description="ID do piquete de destino")
    movement_date: str = Field(..., description="Data da movimentação no formato AAAA-MM-DD")
    reason: Optional[str] = Field(default="manejo", description="Motivo da movimentação (default: manejo)")
    notes: Optional[str] = Field(default="", description="Observações opcionais")


class MovimentarOutput(BaseModel):
    movidos: list[str]
    ja_no_destino: list[str]
    erros: list[str]


class PhotoSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    taken_date: str
    mime: str


@dataclass
class PhotoUploadInput:
    arquivo: UploadFile = File(..., description="Arquivo da foto do animal (JPEG ou PNG, até 5 MB)")
    taken_date: Optional[str] = Form(None, description="Data em que a foto foi tirada")


class PhotoUploadOutput(BaseModel):
    id: int


class ProtocoloOutput(BaseModel):
    id: int
    nome: str
    via: str
    carencia_dias: int
    unidade_dose: str
    dose_sugerida: Optional[float] = None


class MedicamentoInput(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    medicamento: str
    dose: float
    unidade: str
    via: str
    carencia_dias: int
    data: str
    protocolo_id: Optional[int] = None
    notas: Optional[str] = None


class AplicacaoMedicamentoOutput(BaseModel):
    medicamento: str
    dose: float
    unidade: str
    via: str
    carencia_dias: int
    data: str
    protocolo_id: Optional[int] = None


class MedicamentosOutput(BaseModel):
    carencia_ate: Optional[str] = None
    aplicacoes: list[AplicacaoMedicamentoOutput]


class CarenciaOutput(BaseModel):
    carencia_ate: Optional[str] = None


class TratoPendenteOutput(BaseModel):
    plano_id: int
    lote_id: str
    lote_nome: str
    produto: str
    quantidade: float
    unidade: str
    frequencia: str
    insumo_id: Optional[int] = None
    confirmado_no_periodo: bool
    ultima_confirmacao: Optional[str] = None


class ConfirmarTratoInput(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    situacao: Literal["feito", "parcial", "nao_feito"]
    quantidade_aplicada: float
    baixar_estoque: bool
    notas: Optional[str] = None


class PesagemAceita(BaseModel):
    animal_id: str
    peso: float
    data: str
    alertas: list[str] = Field(default_factory=list)


class PesagemRejeitada(BaseModel):
    linha: int
    conteudo: str
    motivo: str


class ImportarPesagensOutput(BaseModel):
    total_linhas: int
    aceitas: list[PesagemAceita]
    rejeitadas: list[PesagemRejeitada]
    gravadas: int


class AlertaSumidoOutput(BaseModel):
    animal_id: str
    breed: str
    lote_id: Optional[str] = None
    peso_atual: float
    dias_sem_pesagem: int


class AlertaCarenciaOutput(BaseModel):
    animal_id: str
    breed: str
    carencia_ate: str
    dias_restantes: int


class AlertaAbateOutput(BaseModel):
    animal_id: str
    breed: str
    peso_atual: float
    peso_alvo: float
    arrobas: float


class AlertaEstoqueBaixoOutput(BaseModel):
    insumo_id: int
    nome: str
    estoque_atual: float
    estoque_minimo: float
    unidade: str


class AlertaBaixoDesempenhoOutput(BaseModel):
    animal_id: str
    breed: str
    lote_id: Optional[str] = None
    peso_atual: float
    gmd: float
    meta_gmd: float


class AlertasOutput(BaseModel):
    sumidos: list[AlertaSumidoOutput]
    carencia: list[AlertaCarenciaOutput]
    prontos_para_abate: list[AlertaAbateOutput]
    estoque_baixo: list[AlertaEstoqueBaixoOutput]
    baixo_desempenho: list[AlertaBaixoDesempenhoOutput]


class TransicaoPermitida(BaseModel):
    para: str
    exige_motivo: bool
    exige_autorizacao: bool


class DispositivoOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    codigo_visual: str
    tipo: str
    status: str
    lote: Optional[str] = None
    transicoes_permitidas: list[TransicaoPermitida]


class MudarStatusDispositivoInput(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    novo_status: str
    motivo: Optional[str] = None


class MudarStatusDispositivoOutput(BaseModel):
    ok: bool
    de: str
    para: str


