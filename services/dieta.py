from __future__ import annotations

from .constantes import KG_PER_ARROBA


def _validar_ingrediente(ingrediente: dict) -> None:
    pct = float(ingrediente.get("materia_seca_pct", 0))
    if pct < 0 or pct > 100:
        raise ValueError(
            f"materia_seca_pct fora de faixa: {pct}. Deve estar entre 0 e 100."
        )


def _round(valor: float) -> float:
    return round(valor, 2)


def _kg_materia_seca(quantidade_kg: float, materia_seca_pct: float) -> float:
    return quantidade_kg * materia_seca_pct / 100.0


def custo_por_cabeca_dia(ingredientes: list[dict]) -> dict:
    ingredientes = ingredientes or []

    if not ingredientes:
        return {
            "custo_dia": 0.0,
            "kg_materia_natural": 0.0,
            "kg_materia_seca": 0.0,
            "participacao": [],
        }

    total_custo = 0.0
    total_materia_natural = 0.0
    total_materia_seca = 0.0
    participacoes = []

    for ingrediente in ingredientes:
        quantidade = float(ingrediente.get("quantidade_kg_cabeca_dia", 0.0))
        custo_kg = float(ingrediente.get("custo_por_kg", 0.0))
        pct = float(ingrediente.get("materia_seca_pct", 0.0))

        _validar_ingrediente(ingrediente)

        custo = quantidade * custo_kg
        kg_seca = _kg_materia_seca(quantidade, pct)

        total_custo += custo
        total_materia_natural += quantidade
        total_materia_seca += kg_seca
        participacoes.append({
            "nome": str(ingrediente.get("nome", "")),
            "pct_custo": custo,
        })

    if total_custo <= 0:
        participacao = [
            {"nome": p["nome"], "pct_custo": 0.0}
            for p in participacoes
        ]
    else:
        participacao = [
            {
                "nome": p["nome"],
                "pct_custo": _round(p["pct_custo"] / total_custo * 100.0),
            }
            for p in participacoes
        ]

        participacao = sorted(participacao, key=lambda item: item["pct_custo"], reverse=True)

        soma_pct = sum(item["pct_custo"] for item in participacao)
        diferenca = _round(100.0 - soma_pct)
        if abs(diferenca) >= 0.01 and participacao:
            participacao[0]["pct_custo"] = _round(participacao[0]["pct_custo"] + diferenca)

    return {
        "custo_dia": _round(total_custo),
        "kg_materia_natural": _round(total_materia_natural),
        "kg_materia_seca": _round(total_materia_seca),
        "participacao": participacao,
    }


def custo_por_arroba_produzida(custo_dia: float, gmd: float,
                               rendimento_carcaca: float) -> float | None:
    custo_dia = float(custo_dia)
    gmd = float(gmd)
    rendimento = float(rendimento_carcaca)

    if gmd <= 0:
        return None

    arrobas = gmd * rendimento / KG_PER_ARROBA
    if arrobas <= 0:
        return None

    return _round(custo_dia / arrobas)
