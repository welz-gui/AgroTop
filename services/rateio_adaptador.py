"""Serviço adaptador para cálculo de dias no lote para rateio (função pura).

Acresce o campo `dias_no_lote: int` aos dicionários de animais para uso no
critério `"peso_dia"` de `services.rateio.ratear()`.
"""

from datetime import date
from typing import Any


def _parse_date(valor: Any) -> date | None:
    if isinstance(valor, date):
        return valor
    if isinstance(valor, str) and len(valor) >= 10:
        try:
            return date.fromisoformat(valor[:10])
        except (ValueError, TypeError):
            return None
    return None


def com_dias_no_lote(
    animais: list[dict],
    referencia: str,
) -> list[dict]:
    """Devolve uma nova lista de dicts com todos os campos originais mantidos e `dias_no_lote: int` acrescido.

    Parâmetros:
    - `animais`: lista de dicionários de animais (ex: {"id": str, "peso": float, "entrada_no_lote": "AAAA-MM-DD" | None}).
    - `referencia`: string ISO "AAAA-MM-DD" da data de referência (ex: hoje ou data do rateio).

    Regras:
    - `dias_no_lote` é calculado como `(referencia - entrada_no_lote).days`.
    - `entrada_no_lote` ausente (`None`), inválida ou posterior a `referencia` produz `dias_no_lote = 0` (nunca negativo).
    - Preserva intactos todos os demais campos do dicionário de cada animal.
    """
    if not isinstance(animais, list):
        return []

    dt_ref = _parse_date(referencia)

    resultado = []
    for item in animais:
        if not isinstance(item, dict):
            continue

        novo_item = dict(item)
        if dt_ref is None:
            novo_item["dias_no_lote"] = 0
            resultado.append(novo_item)
            continue

        raw_entrada = item.get("entrada_no_lote")
        dt_entrada = _parse_date(raw_entrada)

        if dt_entrada is None or dt_entrada > dt_ref:
            dias = 0
        else:
            dias = max(0, (dt_ref - dt_entrada).days)

        novo_item["dias_no_lote"] = int(dias)
        resultado.append(novo_item)

    return resultado
