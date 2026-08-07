"""Serviço adaptador para agrupamento de chuva e GMD por período (função pura).

Agrupa leituras de chuva e pesagens por mês-calendário (AAAA-MM) para consumo
pela função `services.projecao.correlacao_chuva_gmd()`.
"""

from datetime import date
from typing import Any


def _extrair_data(valor: Any) -> str | None:
    if isinstance(valor, date):
        return valor.isoformat()
    if isinstance(valor, str) and len(valor) >= 10:
        return valor[:10]
    return None


def series_mensais(
    leituras_de_chuva: list[dict],
    pesagens: list[dict],
) -> list[dict]:
    """Agrupa leituras de chuva e pesagens por mês-calendário (AAAA-MM).

    Retorna uma lista de dicts:
    [{"periodo": "AAAA-MM", "chuva_mm": float, "gmd_medio": float}, ...]

    Regras:
    - Um mês só é incluído se possuir AO MENOS UMA leitura de chuva E ao menos um par
      consecutivo de pesagens do mesmo animal dentro do próprio mês.
    - Pares de pesagens que cruzam a fronteira do mês (ex: 28/07 e 03/08) são descartados.
    - `chuva_mm` é a soma total das leituras do mês.
    - `gmd_medio` é a média simples dos GMDs dos pares calculados dentro do mês.
    - A lista resultante é ordenada por `periodo` ("AAAA-MM").
    """
    if not isinstance(leituras_de_chuva, list):
        leituras_de_chuva = []
    if not isinstance(pesagens, list):
        pesagens = []

    chuva_por_mes: dict[str, float] = {}
    for leitura in leituras_de_chuva:
        if not isinstance(leitura, dict):
            continue
        dt_str = _extrair_data(leitura.get("read_date") or leitura.get("date") or leitura.get("data"))
        if not dt_str:
            continue

        mes = dt_str[:7]

        raw_rain = (
            leitura.get("rain_mm")
            if leitura.get("rain_mm") is not None
            else leitura.get("chuva_mm", leitura.get("volume"))
        )
        try:
            rain = float(raw_rain)
        except (ValueError, TypeError):
            continue

        if rain < 0:
            continue

        chuva_por_mes[mes] = chuva_por_mes.get(mes, 0.0) + rain

    pesagens_por_animal: dict[str, list[tuple[date, float]]] = {}
    for p in pesagens:
        if not isinstance(p, dict):
            continue
        animal_id = str(
            p.get("animal_uuid")
            if p.get("animal_uuid") is not None
            else p.get("animal_id", p.get("id"))
        )
        dt_str = _extrair_data(p.get("weigh_date") or p.get("date") or p.get("data"))
        raw_peso = (
            p.get("weight")
            if p.get("weight") is not None
            else p.get("peso")
        )
        if not animal_id or not dt_str or raw_peso is None:
            continue

        try:
            d = date.fromisoformat(dt_str)
            peso = float(raw_peso)
        except (ValueError, TypeError):
            continue

        if animal_id not in pesagens_por_animal:
            pesagens_por_animal[animal_id] = []
        pesagens_por_animal[animal_id].append((d, peso))

    gmds_por_mes: dict[str, list[float]] = {}
    for animal_id, lista in pesagens_por_animal.items():
        lista_ordenada = sorted(lista, key=lambda item: item[0])
        for i in range(len(lista_ordenada) - 1):
            d1, p1 = lista_ordenada[i]
            d2, p2 = lista_ordenada[i + 1]

            mes1 = d1.strftime("%Y-%m")
            mes2 = d2.strftime("%Y-%m")

            if mes1 != mes2:
                continue

            dias = (d2 - d1).days
            if dias <= 0:
                continue

            gmd = (p2 - p1) / dias
            if mes1 not in gmds_por_mes:
                gmds_por_mes[mes1] = []
            gmds_por_mes[mes1].append(gmd)

    todos_meses = sorted(set(chuva_por_mes.keys()) & set(gmds_por_mes.keys()))
    resultado = []

    for mes in todos_meses:
        gmd_lista = gmds_por_mes[mes]
        if not gmd_lista:
            continue

        gmd_medio = sum(gmd_lista) / len(gmd_lista)
        chuva_total = chuva_por_mes[mes]

        resultado.append({
            "periodo": mes,
            "chuva_mm": float(chuva_total),
            "gmd_medio": float(gmd_medio),
        })

    return resultado
