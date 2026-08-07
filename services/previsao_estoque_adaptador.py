"""Serviço adaptador de insumos para previsão de estoque (função pura).

Monta a lista de insumos com consumo diário planejado e prazo de reposição
para ser consumida por `services.previsao_estoque.prever()`.
"""

from typing import Callable, Optional


def consumo_diario_planejado(
    insumos_por_id: dict[int, dict],
    planos_ativos: list[dict],
    converter_quantidade: Callable,
) -> dict[int, float]:
    """Calcula o consumo diário planejado por insumo (kg ou litro por dia).

    - `insumos_por_id`: {id: {"unit": str}}
    - `planos_ativos`: [{"insumo_id": int, "quantity": float, "unit": str, "frequency": str}]
    - `converter_quantidade`: função de conversão (ex: database.convert_quantity)

    Regras:
    - Frequências válidas: 'diario' (1x/dia), 'semanal' (1/7 por dia), 'mensal' (1/30 por dia).
    - Frequência desconhecida ou fora de {"diario", "semanal", "mensal"} faz o plano
      ser IGNORADO (não contribui à soma).
    - Plano cuja unidade não converte para a do insumo é IGNORADO.
    - Insumo sem planos ativos ou com planos ignorados permanece no dict com consumo 0.0.
    """
    fatores_frequencia = {
        "diario": 1.0,
        "semanal": 1.0 / 7.0,
        "mensal": 1.0 / 30.0,
    }

    resultado = {insumo_id: 0.0 for insumo_id in insumos_por_id}

    if not isinstance(planos_ativos, list):
        return resultado

    for plano in planos_ativos:
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

        unidade_insumo = insumo_info.get("unit") or insumo_info.get("unidade")
        unidade_plano = plano.get("unit") or plano.get("unidade")
        raw_qty = (
            plano.get("quantity")
            if plano.get("quantity") is not None
            else plano.get("quantidade")
        )

        try:
            qty = float(raw_qty)
        except (ValueError, TypeError):
            continue

        if qty <= 0:
            continue

        freq_raw = plano.get("frequency") or plano.get("frequencia")
        if not isinstance(freq_raw, str):
            continue

        freq_norm = freq_raw.strip().lower()
        if freq_norm not in fatores_frequencia:
            continue

        fator_freq = fatores_frequencia[freq_norm]

        if unidade_insumo and unidade_plano and unidade_insumo == unidade_plano:
            qty_convertida = qty
        else:
            if not callable(converter_quantidade):
                continue
            try:
                qty_convertida = converter_quantidade(
                    qty, unidade_plano, unidade_insumo
                )
            except Exception:
                qty_convertida = None

        if qty_convertida is None:
            continue

        try:
            qty_convertida = float(qty_convertida)
        except (ValueError, TypeError):
            continue

        resultado[insumo_id] += qty_convertida * fator_freq

    return resultado


def montar_insumos(
    insumos: list[dict],
    consumo_por_id: dict[int, float],
    prazos_de_reposicao: Optional[dict[int, int]] = None,
) -> list[dict]:
    """Monta a lista final de insumos para `services.previsao_estoque.prever()`.

    `insumos`: linhas de `insumos` (dict com id, name/nome, unit/unidade,
      current_stock/saldo, min_stock/estoque_minimo).
    `consumo_por_id`: dict de saída de `consumo_diario_planejado()`.
    `prazos_de_reposicao`: dict {insumo_id: dias}. Se omitido ou None, assume 0.
    """
    if not isinstance(insumos, list):
        return []

    if not isinstance(consumo_por_id, dict):
        consumo_por_id = {}

    if not isinstance(prazos_de_reposicao, dict):
        prazos_de_reposicao = {}

    resultado = []
    for item in insumos:
        if not isinstance(item, dict):
            continue

        insumo_id = item.get("id")
        nome = str(item.get("name") or item.get("nome") or "")
        unidade = str(item.get("unit") or item.get("unidade") or "")

        raw_stock = (
            item.get("current_stock")
            if item.get("current_stock") is not None
            else item.get("saldo", 0.0)
        )
        try:
            saldo = float(raw_stock)
        except (ValueError, TypeError):
            saldo = 0.0

        raw_min = (
            item.get("min_stock")
            if item.get("min_stock") is not None
            else item.get("estoque_minimo", 0.0)
        )
        try:
            estoque_minimo = float(raw_min)
        except (ValueError, TypeError):
            estoque_minimo = 0.0

        try:
            consumo_diario = float(consumo_por_id.get(insumo_id, 0.0))
        except (ValueError, TypeError):
            consumo_diario = 0.0

        try:
            prazo_reposicao = int(prazos_de_reposicao.get(insumo_id, 0))
        except (ValueError, TypeError):
            prazo_reposicao = 0

        resultado.append({
            "id": insumo_id,
            "nome": nome,
            "unidade": unidade,
            "saldo": saldo,
            "consumo_diario": consumo_diario,
            "estoque_minimo": estoque_minimo,
            "prazo_reposicao_dias": prazo_reposicao,
        })

    return resultado
