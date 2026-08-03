"""Projeções de abate e associação entre chuva e GMD."""

import math
from datetime import date, timedelta


def projetar_abate(peso_atual: float, peso_alvo: float, gmd: float,
                   hoje: str) -> dict:
    """Quando o animal atinge o peso-alvo, no ritmo atual."""
    data_hoje = date.fromisoformat(hoje)

    if peso_atual >= peso_alvo:
        return {
            "dias_restantes": 0,
            "data_prevista": data_hoje.isoformat(),
            "situacao": "pronto",
        }
    if gmd is None or gmd == 0:
        return {
            "dias_restantes": None,
            "data_prevista": None,
            "situacao": "sem_ganho",
        }
    if gmd < 0:
        return {
            "dias_restantes": None,
            "data_prevista": None,
            "situacao": "perdendo_peso",
        }

    dias = math.ceil((peso_alvo - peso_atual) / gmd)
    return {
        "dias_restantes": dias,
        "data_prevista": (data_hoje + timedelta(days=dias)).isoformat(),
        "situacao": "projetado",
    }


def projetar_lote(animais: list[dict], hoje: str) -> dict:
    """Projeção agregada de um lote."""
    projecoes = []
    sem_projecao = []
    prontos = 0

    for animal in animais:
        resultado = projetar_abate(
            animal["peso_atual"],
            animal["peso_alvo"],
            animal.get("gmd"),
            hoje,
        )
        if resultado["situacao"] == "pronto":
            prontos += 1
        if resultado["data_prevista"] is None:
            sem_projecao.append(str(animal["id"]))
        else:
            projecoes.append(resultado)

    datas = [item["data_prevista"] for item in projecoes]
    dias = [item["dias_restantes"] for item in projecoes]
    lote_completo = bool(animais) and not sem_projecao
    return {
        "prontos": prontos,
        "data_primeiro": min(datas) if datas else None,
        "data_ultimo": max(datas) if datas else None,
        "dias_ate_lote_completo": max(dias) if lote_completo else None,
        "sem_projecao": sem_projecao,
    }


def _interpretar(coeficiente: float, n: int) -> str:
    magnitude = abs(coeficiente)
    if magnitude < 0.20:
        forca = "muito fraca"
    elif magnitude < 0.40:
        forca = "fraca"
    elif magnitude < 0.60:
        forca = "moderada"
    elif magnitude < 0.80:
        forca = "forte"
    else:
        forca = "muito forte"

    if coeficiente > 0:
        relacao = f"{forca} e positiva"
    elif coeficiente < 0:
        relacao = f"{forca} e negativa"
    else:
        relacao = f"{forca}, sem direção linear"

    if n < 6:
        return (
            f"Amostra pequena (n={n}): a associação linear é {relacao}, "
            "mas a estimativa é instável. Correlação não demonstra causalidade."
        )
    return (
        f"Em {n} períodos, a associação linear é {relacao}. "
        "Correlação não demonstra causalidade."
    )


def correlacao_chuva_gmd(series: list[dict]) -> dict:
    """Relação entre chuva do período e ganho médio."""
    n = len(series)
    if n < 3:
        return {
            "coeficiente": None,
            "n": n,
            "interpretacao": (
                f"Amostra pequena (n={n}): são necessários ao menos 3 períodos "
                "para calcular a correlação; não é possível avaliar associação "
                "ou causalidade."
            ),
        }

    chuvas = [float(item["chuva_mm"]) for item in series]
    gmds = [float(item["gmd_medio"]) for item in series]
    media_chuva = sum(chuvas) / n
    media_gmd = sum(gmds) / n
    desvios_chuva = [valor - media_chuva for valor in chuvas]
    desvios_gmd = [valor - media_gmd for valor in gmds]
    soma_quadrados_chuva = sum(valor ** 2 for valor in desvios_chuva)
    soma_quadrados_gmd = sum(valor ** 2 for valor in desvios_gmd)

    if soma_quadrados_chuva == 0 or soma_quadrados_gmd == 0:
        return {
            "coeficiente": None,
            "n": n,
            "interpretacao": (
                "Não há variação suficiente em chuva ou GMD para calcular a "
                "correlação; não é possível avaliar associação ou causalidade."
            ),
        }

    numerador = sum(
        chuva * gmd for chuva, gmd in zip(desvios_chuva, desvios_gmd)
    )
    coeficiente = numerador / math.sqrt(
        soma_quadrados_chuva * soma_quadrados_gmd
    )
    coeficiente = max(-1.0, min(1.0, coeficiente))
    return {
        "coeficiente": coeficiente,
        "n": n,
        "interpretacao": _interpretar(coeficiente, n),
    }
