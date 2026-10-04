"""Serviço adaptador de ingredientes do trato para cálculo de dieta (função pura).

Converte planos de nutrição (por piquete) e insumos para a lista de ingredientes
por cabeça consumida por `services.dieta.custo_por_cabeca_dia()`.
"""

from typing import Callable, Optional

_FATORES_FREQUENCIA = {
    "diario": 1.0,
    "semanal": 1.0 / 7.0,
    "mensal": 1.0 / 30.0,
}


def _obter_cabecas_validas(cabecas_no_piquete: int) -> int:
    try:
        cabecas = int(cabecas_no_piquete)
        return cabecas if cabecas > 0 else 0
    except (ValueError, TypeError):
        return 0


def _obter_fator_frequencia(plano: dict) -> Optional[float]:
    freq_raw = plano.get("frequency") or plano.get("frequencia")
    if not isinstance(freq_raw, str):
        return None
    return _FATORES_FREQUENCIA.get(freq_raw.strip().lower())


def _obter_quantidade(plano: dict) -> Optional[float]:
    raw_qty = (
        plano.get("quantity")
        if plano.get("quantity") is not None
        else plano.get("quantidade")
    )
    try:
        qty = float(raw_qty)
        return qty if qty > 0 else None
    except (ValueError, TypeError):
        return None


def _converter_unidade(
    qty: float, unit_plano: str, unit_insumo: str, converter_quantidade: Optional[Callable]
) -> Optional[float]:
    unit_p = (unit_plano or "").strip().lower()
    unit_i = (unit_insumo or "").strip().lower()

    if unit_p and unit_i and unit_p == unit_i:
        qty_convertida = qty
    elif callable(converter_quantidade):
        try:
            qty_convertida = converter_quantidade(qty, unit_p, unit_i)
        except Exception:
            return None
    elif (unit_p == "g" and unit_i == "kg") or (unit_p == "ml" and unit_i in ("l", "litro")):
        qty_convertida = qty / 1000.0
    elif (unit_p == "kg" and unit_i == "g") or (unit_p in ("t", "ton") and unit_i == "kg"):
        qty_convertida = qty * 1000.0
    else:
        return None

    if qty_convertida is None:
        return None

    try:
        return float(qty_convertida)
    except (ValueError, TypeError):
        return None


def _montar_ingrediente(item: dict) -> dict:
    info = item["info"]
    nome = str(info.get("name") or info.get("nome") or info.get("product_name") or "")

    raw_custo = (
        info.get("cost_per_unit")
        if info.get("cost_per_unit") is not None
        else info.get("custo_unitario", 0.0)
    )
    try:
        custo_por_kg = float(raw_custo)
    except (ValueError, TypeError):
        custo_por_kg = 0.0

    try:
        materia_seca_pct = float(info.get("materia_seca_pct", 0.0))
    except (ValueError, TypeError):
        materia_seca_pct = 0.0

    return {
        "nome": nome,
        "quantidade_kg_cabeca_dia": item["total_qty_cabeca_dia"],
        "custo_por_kg": custo_por_kg,
        "materia_seca_pct": materia_seca_pct,
    }


def ingredientes_por_cabeca(
    planos_do_piquete: list[dict],
    insumos_por_id: dict[int, dict],
    cabecas_no_piquete: int,
    converter_quantidade: Optional[Callable] = None,
) -> list[dict]:
    """Monta a lista de ingredientes por cabeça/dia para `services.dieta.custo_por_cabeca_dia()`.

    Parâmetros:
    - `planos_do_piquete`: lista de dicts de `feeding_plans` (com insumo_id, quantity, unit, frequency, active).
    - `insumos_por_id`: dict {id: {"name": str, "unit": str, "cost_per_unit": float, "materia_seca_pct": float}}.
    - `cabecas_no_piquete`: número de cabeças no piquete.
    - `converter_quantidade`: função opcional para conversão de unidades (ex: database.convert_quantity).

    Regras:
    - Se `cabecas_no_piquete <= 0`, retorna lista vazia `[]`.
    - Ignora planos com `active == False` ou `insumo_id` ausente em `insumos_por_id`.
    - Ignora planos com frequência fora de {"diario", "semanal", "mensal"}.
    - Ignora planos com unidade incompatível (sem conversão conhecida para a unidade do insumo).
    - Se `materia_seca_pct` estiver ausente no insumo, assume 0.0 (zera `kg_materia_seca` no
      resultado até que o dado seja adicionado ao schema).
    - Agrupa por `insumo_id` somando as quantidades por cabeça/dia antes de retornar.
    """
    cabecas = _obter_cabecas_validas(cabecas_no_piquete)
    if cabecas == 0:
        return []

    if not isinstance(planos_do_piquete, list) or not isinstance(insumos_por_id, dict):
        return []

    agrupado: dict[int, dict] = {}
    ordem_insumos: list[int] = []

    for plano in planos_do_piquete:
        if not isinstance(plano, dict):
            continue

        if plano.get("active") is False or plano.get("ativo") is False:
            continue

        insumo_id = plano.get("insumo_id")
        if insumo_id not in insumos_por_id:
            continue

        insumo_info = insumos_por_id[insumo_id]
        if not isinstance(insumo_info, dict):
            continue

        fator_freq = _obter_fator_frequencia(plano)
        if fator_freq is None:
            continue

        qty = _obter_quantidade(plano)
        if qty is None:
            continue

        qty_convertida = _converter_unidade(
            qty,
            plano.get("unit") or plano.get("unidade"),
            insumo_info.get("unit") or insumo_info.get("unidade"),
            converter_quantidade,
        )
        if qty_convertida is None:
            continue

        qty_cabeca_dia = (qty_convertida * fator_freq) / cabecas

        if insumo_id not in agrupado:
            agrupado[insumo_id] = {
                "total_qty_cabeca_dia": 0.0,
                "info": insumo_info,
            }
            ordem_insumos.append(insumo_id)

        agrupado[insumo_id]["total_qty_cabeca_dia"] += qty_cabeca_dia

    return [_montar_ingrediente(agrupado[iid]) for iid in ordem_insumos]
