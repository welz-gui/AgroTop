from __future__ import annotations
from fractions import Fraction
import math
from typing import List, Dict


def ratear(valor_total: float, animais: List[Dict], criterio: str) -> List[Dict]:
    if not animais:
        return []

    if criterio not in ("igual", "peso", "peso_dia"):
        raise ValueError("criterio must be 'igual', 'peso' or 'peso_dia'")

    # build weights
    weights: List[Fraction] = []
    for a in animais:
        if criterio == "igual":
            w = Fraction(1)
        elif criterio == "peso":
            w = Fraction(str(a.get("peso", 0)))
        else:  # peso_dia
            w = Fraction(str(a.get("peso", 0))) * Fraction(int(a.get("dias_no_lote", 0)))
        weights.append(w)

    total_weight = sum(weights, Fraction(0))
    if total_weight == 0:
        weights = [Fraction(1) for _ in animais]
        total_weight = sum(weights, Fraction(0))

    total_cents = int(round(float(valor_total) * 100))

    # compute fractional shares in cents using exact rational arithmetic
    shares_frac = [Fraction(total_cents) * w / total_weight for w in weights]
    floor_shares = [math.floor(float(s)) for s in shares_frac]
    sum_floor = sum(floor_shares)
    remainder = total_cents - sum_floor

    # fractional parts for tie-breaking
    fractional_parts = [shares_frac[i] - Fraction(floor_shares[i]) for i in range(len(animais))]

    # indices sorted by fractional part descending, tie-breaking by original index
    indices = sorted(range(len(animais)), key=lambda i: (fractional_parts[i], -i), reverse=True)

    # start with floor allocations and add one cent to the top 'remainder' indices
    final_cents = floor_shares[:]
    for i in range(remainder):
        final_cents[indices[i]] += 1

    # build result preserving requested keys
    result = []
    for idx, a in enumerate(animais):
        valor = final_cents[idx] / 100.0
        result.append({"animal_id": str(a.get("id")), "valor": round(valor, 2)})

    return result
