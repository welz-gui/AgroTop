"""Serviço adaptador de ingredientes do trato para cálculo de dieta (função pura).

Converte planos de nutrição (por piquete) e insumos para a lista de ingredientes
por cabeça consumida por `services.dieta.custo_por_cabeca_dia()`.
"""

from typing import Callable, Optional


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
    try:
        cabecas = int(cabecas_no_piquete)
    except (ValueError, TypeError):
        return []

    if cabecas <= 0:
        return []

    if not isinstance(planos_do_piquete, list) or not isinstance(insumos_por_id, dict):
        return []

    fatores_frequencia = {
        "diario": 1.0,
        "semanal": 1.0 / 7.0,
        "mensal": 1.0 / 30.0,
    }

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

        freq_raw = plano.get("frequency") or plano.get("frequencia")
        if not isinstance(freq_raw, str):
            continue

        freq_norm = freq_raw.strip().lower()
        if freq_norm not in fatores_frequencia:
            continue

        fator_freq = fatores_frequencia[freq_norm]

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

        unit_plano = (plano.get("unit") or plano.get("unidade") or "").strip().lower()
        unit_insumo = (insumo_info.get("unit") or insumo_info.get("unidade") or "").strip().lower()

        if unit_plano and unit_insumo and unit_plano == unit_insumo:
            qty_convertida = qty
        elif callable(converter_quantidade):
            try:
                qty_convertida = converter_quantidade(qty, unit_plano, unit_insumo)
            except Exception:
                qty_convertida = None
        elif (unit_plano == "g" and unit_insumo == "kg") or (unit_plano == "ml" and unit_insumo in ("l", "litro")):
            qty_convertida = qty / 1000.0
        elif (unit_plano == "kg" and unit_insumo == "g") or (unit_plano in ("t", "ton") and unit_insumo == "kg"):
            qty_convertida = qty * 1000.0
        else:
            qty_convertida = None

        if qty_convertida is None:
            continue

        try:
            qty_convertida = float(qty_convertida)
        except (ValueError, TypeError):
            continue

        qty_diaria_piquete = qty_convertida * fator_freq
        qty_cabeca_dia = qty_diaria_piquete / cabecas

        if insumo_id not in agrupado:
            agrupado[insumo_id] = {
                "total_qty_cabeca_dia": 0.0,
                "info": insumo_info,
            }
            ordem_insumos.append(insumo_id)

        agrupado[insumo_id]["total_qty_cabeca_dia"] += qty_cabeca_dia

    resultado = []
    for iid in ordem_insumos:
        item = agrupado[iid]
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

        resultado.append({
            "nome": nome,
            "quantidade_kg_cabeca_dia": item["total_qty_cabeca_dia"],
            "custo_por_kg": custo_por_kg,
            "materia_seca_pct": materia_seca_pct,
        })

    return resultado
