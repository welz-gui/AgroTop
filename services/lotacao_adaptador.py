"""Adaptador para montar dados de lote/piquete para `services/lotacao.py` (função pura).

Agrupa animais ativos por lote e estrutura a entrada esperada por `lotacao()` e `avaliar_lotacao()`.
"""


def _safe_float(val, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def por_lote(
    animais: list[dict],
    lotes: list[dict],
) -> dict[str, dict]:
    """Agrupa animais ativos por lote.

    Retorna:
        {lote_id_str: {"area_ha": float, "animais": [{"peso": float}, ...]}}

    - Apenas animais com `status == "ativo"` são incluídos.
    - Lotes sem nenhum animal ativo aparecem no dict com `"animais": []`.
    - Animais sem `lote_id` ou com `lote_id` inexistente na lista de `lotes` são descartados.
    """
    if not isinstance(lotes, list) or not lotes:
        return {}

    resultado: dict[str, dict] = {}
    mapa_lotes_id: dict[str, str] = {}

    for lote in lotes:
        if not isinstance(lote, dict):
            continue

        raw_id = lote.get("id")
        if raw_id is None:
            continue

        lote_id_str = str(raw_id)
        area_ha = _safe_float(lote.get("area_ha"))
        mapa_lotes_id[lote_id_str] = lote_id_str
        resultado[lote_id_str] = {
            "area_ha": area_ha,
            "animais": [],
        }

    if not isinstance(animais, list) or not animais:
        return resultado

    for animal in animais:
        if not isinstance(animal, dict):
            continue

        status = str(animal.get("status", "")).strip().lower()
        if status != "ativo":
            continue

        raw_lote_id = animal.get("lote_id")
        if raw_lote_id is None:
            continue

        lote_id_str = str(raw_lote_id)
        if lote_id_str not in mapa_lotes_id:
            continue

        peso = _safe_float(animal.get("peso"), 0.0)
        resultado[lote_id_str]["animais"].append({"peso": peso})

    return resultado
