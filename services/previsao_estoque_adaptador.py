"""Adaptador para montar os dados esperados por `services/previsao_estoque.py` (função pura).

Esta biblioteca transforma dados brutos de tabelas (insumos, feeding_plans) na estrutura
esperada por `services.previsao_estoque.prever()`, sem tocar banco ou alterar o schema.
"""

_FREQ_POR_DIA = {
    "diario": 1.0,
    "semanal": 1.0 / 7.0,
    "mensal": 1.0 / 30.0,
}


def _safe_float(val, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _safe_int(val, default: int = 0) -> int:
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def consumo_diario_planejado(
    insumos_por_id: dict[int, dict],
    planos_ativos: list[dict],
    converter_quantidade,
) -> dict[int, float]:
    """Calcula a soma do consumo diário planejado de cada insumo com base nos planos ativos.

    - `insumos_por_id`: {id: {"unit": str, ...}}
    - `planos_ativos`: [{"insumo_id": int, "quantity": float, "unit": str, "frequency": str}, ...]
    - `converter_quantidade`: função de conversão de unidade (ex.: `database.convert_quantity`)
    """
    if not insumos_por_id or not planos_ativos or not callable(converter_quantidade):
        return {}

    consumo: dict[int, float] = {}

    for plano in planos_ativos:
        if not isinstance(plano, dict):
            continue

        iid = plano.get("insumo_id")
        if iid is None or iid not in insumos_por_id:
            continue

        insumo = insumos_por_id[iid]
        if not isinstance(insumo, dict):
            continue

        unit_dest = insumo.get("unit") or insumo.get("unidade")
        unit_orig = plano.get("unit") or plano.get("unidade")
        qtd_raw = _safe_float(plano.get("quantity") if "quantity" in plano else plano.get("quantidade"))

        qtd_convertida = converter_quantidade(qtd_raw, unit_orig, unit_dest)
        if qtd_convertida is None:
            continue

        freq_str = str(plano.get("frequency") or plano.get("frequencia") or "").lower()
        fator_freq = _FREQ_POR_DIA.get(freq_str, 1.0)

        qtd_diaria = float(qtd_convertida) * fator_freq
        consumo[iid] = consumo.get(iid, 0.0) + qtd_diaria

    return consumo


def montar_insumos(
    insumos: list[dict],
    consumo_por_id: dict[int, float],
    prazos_de_reposicao: dict[int, int] | None = None,
) -> list[dict]:
    """Monta a lista final de insumos para `services.previsao_estoque.prever()`.

    - `insumos`: [{"id": int, "name": str, "unit": str, "current_stock": float, "min_stock": float}, ...]
    - `consumo_por_id`: {insumo_id: consumo_diario_float}
    - `prazos_de_reposicao`: {insumo_id: dias_int} (opcional, assume 0 se ausente)
    """
    if not isinstance(insumos, list):
        return []

    prazos = prazos_de_reposicao if isinstance(prazos_de_reposicao, dict) else {}
    consumo_dict = consumo_por_id if isinstance(consumo_por_id, dict) else {}

    resultado = []
    for item in insumos:
        if not isinstance(item, dict):
            continue

        iid = item.get("id")
        nome = str(item.get("name") if "name" in item else item.get("nome", ""))
        unidade = str(item.get("unit") if "unit" in item else item.get("unidade", ""))
        saldo = _safe_float(item.get("current_stock") if "current_stock" in item else item.get("saldo"))
        estoque_minimo = _safe_float(item.get("min_stock") if "min_stock" in item else item.get("estoque_minimo"))
        consumo_diario = _safe_float(consumo_dict.get(iid, 0.0))
        prazo_reposicao_dias = _safe_int(prazos.get(iid, 0))

        resultado.append({
            "id": iid,
            "nome": nome,
            "unidade": unidade,
            "saldo": saldo,
            "consumo_diario": consumo_diario,
            "estoque_minimo": estoque_minimo,
            "prazo_reposicao_dias": prazo_reposicao_dias,
        })

    return resultado
