"""Modelos Pydantic (schemas) da API Backend AgroTop."""

from typing import Optional, Union
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
