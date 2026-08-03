"""Indicadores de rentabilidade de ciclos encerrados, agrupados por raça."""

from datetime import date, timedelta

from . import zootecnia
from .constantes import KG_PER_ARROBA


def _gmd_do_ciclo(ciclo: dict) -> float | None:
    dias = int(ciclo["dias"])
    if dias <= 0:
        return None

    # A função canônica recebe a data de entrada; o ciclo já traz a duração.
    entrada = date.today() - timedelta(days=dias)
    return zootecnia.calculate_gmd_total({
        "entry_date": entrada.isoformat(),
        "entry_weight": float(ciclo["peso_entrada"]),
        "current_weight": float(ciclo["peso_saida"]),
    })


def ranking_por_raca(ciclos: list[dict]) -> list[dict]:
    """Rentabilidade por raça, a partir de ciclos ENCERRADOS.

    Ciclos sem receita informada são ignorados porque ainda não têm desfecho.
    Receita zero é mantida como um desfecho válido e resulta em margem zero.
    """
    grupos: dict[str, dict] = {}

    for ciclo in ciclos:
        if ciclo.get("receita") is None:
            continue

        raca = str(ciclo["raca"])
        peso_entrada = float(ciclo["peso_entrada"])
        peso_saida = float(ciclo["peso_saida"])
        custo = float(ciclo["custo_total"])
        receita = float(ciclo["receita"])
        lucro = receita - custo

        grupo = grupos.setdefault(raca, {
            "animais": 0,
            "lucro_total": 0.0,
            "arrobas_produzidas": 0.0,
            "receita_total": 0.0,
            "gmds": [],
        })
        grupo["animais"] += 1
        grupo["lucro_total"] += lucro
        grupo["arrobas_produzidas"] += (
            peso_saida - peso_entrada
        ) / KG_PER_ARROBA
        grupo["receita_total"] += receita

        gmd = _gmd_do_ciclo(ciclo)
        if gmd is not None:
            grupo["gmds"].append(gmd)

    resultado = []
    for raca, grupo in grupos.items():
        animais = grupo["animais"]
        lucro_total = grupo["lucro_total"]
        arrobas = grupo["arrobas_produzidas"]
        receita_total = grupo["receita_total"]
        gmds = grupo["gmds"]

        margem = lucro_total / receita_total if receita_total > 0 else 0.0
        resultado.append({
            "raca": raca,
            "animais": animais,
            "lucro_por_cabeca": round(lucro_total / animais, 2),
            "lucro_por_arroba_produzida": (
                round(lucro_total / arrobas, 2) if arrobas > 0 else 0.0
            ),
            "gmd_medio": round(sum(gmds) / len(gmds), 3) if gmds else 0.0,
            "margem": round(min(1.0, max(0.0, margem)), 4),
        })

    return sorted(
        resultado,
        key=lambda item: item["lucro_por_cabeca"],
        reverse=True,
    )
