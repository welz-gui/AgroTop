"""Cálculos de lotação, capacidade e sobreposição de piquetes para o AgroTop (função pura)."""

import math
from services.constantes import UA_WEIGHT
from services.geometria import _poligono_projetado, area_hectares, validar


def lotacao(area_ha: float, animais: list[dict]) -> dict:
    """Lotação atual do piquete baseada no peso vivo real dos animais.

    `animais`: [{"id": str, "peso": float}, ...]
    Uma UA = 450 kg de peso vivo (`services.constantes.UA_WEIGHT`).

    Retorna {
      "ua_total": float, "ua_por_ha": float,
      "cabecas": int, "peso_total": float,
    }
    """
    if not isinstance(animais, list):
        animais = []

    area_ha = max(0.0, float(area_ha or 0.0))

    cabecas = 0
    peso_total = 0.0

    for animal in animais:
        if not isinstance(animal, dict):
            continue
        try:
            peso = float(animal.get("peso", 0.0) or 0.0)
            if peso > 0:
                cabecas += 1
                peso_total += peso
        except (ValueError, TypeError):
            continue

    ua_total = peso_total / UA_WEIGHT
    ua_por_ha = (ua_total / area_ha) if area_ha > 0 else 0.0

    return {
        "ua_total": float(round(ua_total, 2)),
        "ua_por_ha": float(round(ua_por_ha, 2)),
        "cabecas": cabecas,
        "peso_total": float(round(peso_total, 2)),
    }


def capacidade(area_ha: float, ua_por_ha_alvo: float) -> dict:
    """Quantas UA e cabeças de 450 kg o piquete comporta na lotação alvo.

    Retorna {"ua_suportadas": float, "cabecas_450kg": int}
    """
    area_ha = max(0.0, float(area_ha or 0.0))
    ua_por_ha_alvo = max(0.0, float(ua_por_ha_alvo or 0.0))

    ua_suportadas = area_ha * ua_por_ha_alvo
    cabecas_450kg = int(math.floor(ua_suportadas))

    return {
        "ua_suportadas": float(round(ua_suportadas, 2)),
        "cabecas_450kg": cabecas_450kg,
    }


def avaliar_lotacao(
    area_ha: float, animais: list[dict], ua_por_ha_alvo: float
) -> dict:
    """Compara lotação atual com a lotação alvo, aplicando tolerância de ±10%.

    Retorna {
      "ua_total": float, "ua_por_ha": float, "cabecas": int, "peso_total": float,
      "ua_suportadas": float, "cabecas_450kg": int,
      "situacao": "ocioso" | "adequado" | "sobrecarregado",
      "folga_ua": float, "mensagem": str,
    }
    """
    dados_lot = lotacao(area_ha, animais)
    dados_cap = capacidade(area_ha, ua_por_ha_alvo)

    ua_atual_ha = dados_lot["ua_por_ha"]
    alvo = max(0.0, float(ua_por_ha_alvo or 0.0))
    folga_ua = float(round(dados_cap["ua_suportadas"] - dados_lot["ua_total"], 2))

    if alvo <= 0:
        if ua_atual_ha > 0:
            situacao = "sobrecarregado"
            msg = "Piquete com animais mas lotação alvo definida como zero."
        else:
            situacao = "adequado"
            msg = "Piquete sem animais e alvo zero."
    else:
        limite_inferior = 0.90 * alvo
        limite_superior = 1.10 * alvo

        if ua_atual_ha < limite_inferior:
            situacao = "ocioso"
            msg = (
                f"Lotação atual de {ua_atual_ha:.2f} UA/ha está abaixo da tolerância "
                f"do alvo de {alvo:.2f} UA/ha (subaproveitado em {folga_ua:.2f} UA)."
            )
        elif ua_atual_ha > limite_superior:
            situacao = "sobrecarregado"
            excesso = abs(folga_ua)
            msg = (
                f"Lotação atual de {ua_atual_ha:.2f} UA/ha excede a tolerância "
                f"do alvo de {alvo:.2f} UA/ha (excesso de {excesso:.2f} UA)."
            )
        else:
            situacao = "adequado"
            msg = (
                f"Lotação atual de {ua_atual_ha:.2f} UA/ha está adequada ao alvo de "
                f"{alvo:.2f} UA/ha (dentro da tolerância de ±10%)."
            )

    resultado = dict(dados_lot)
    resultado.update(dados_cap)
    resultado.update({
        "situacao": situacao,
        "folga_ua": folga_ua,
        "mensagem": msg,
    })
    return resultado


def sobrepostos(piquetes: list[dict]) -> list[dict]:
    """Pares de piquetes cujos polígonos se cruzam.

    `piquetes`: [{"id": str, "anel": [(lon, lat), ...]}, ...]

    Sobreposições abaixo de 1% da área do menor piquete são ignoradas para evitar
    alarmes falsos em bordas compartilhadas ou imperfeições de desenho.

    Retorna [{"a": str, "b": str, "area_sobreposta_ha": float,
              "pct_do_menor": float}, ...], do maior ao menor.
    """
    if not isinstance(piquetes, list):
        return []

    poligonos_validos = []

    for p in piquetes:
        if not isinstance(p, dict):
            continue

        p_id = str(p.get("id", ""))
        anel = p.get("anel")

        if not p_id or not isinstance(anel, list):
            continue

        probs = validar(anel)
        if probs:
            # Polígono inválido é pulado sem derrubar a verificação dos demais
            continue

        try:
            poly_proj, _ = _poligono_projetado(anel)
            area_ha = poly_proj.area / 10_000.0
            if area_ha > 0:
                poligonos_validos.append({
                    "id": p_id,
                    "poly": poly_proj,
                    "area_ha": area_ha,
                })
        except Exception:
            continue

    resultado = []
    n = len(poligonos_validos)

    for i in range(n):
        for j in range(i + 1, n):
            item_a = poligonos_validos[i]
            item_b = poligonos_validos[j]

            poly_a = item_a["poly"]
            poly_b = item_b["poly"]

            if not poly_a.intersects(poly_b):
                continue

            inter_geom = poly_a.intersection(poly_b)
            if inter_geom.is_empty:
                continue

            area_inter_ha = float(inter_geom.area / 10_000.0)
            area_menor_ha = min(item_a["area_ha"], item_b["area_ha"])

            if area_menor_ha <= 0:
                continue

            pct_do_menor = (area_inter_ha / area_menor_ha) * 100.0

            # Descarte de sobreposições insignificantes de borda (< 1%)
            if pct_do_menor < 1.0:
                continue

            resultado.append({
                "a": item_a["id"],
                "b": item_b["id"],
                "area_sobreposta_ha": float(round(area_inter_ha, 4)),
                "pct_do_menor": float(round(pct_do_menor, 2)),
            })

    # Ordenado da maior sobreposição para a menor
    resultado.sort(
        key=lambda x: (x["area_sobreposta_ha"], x["pct_do_menor"]), reverse=True
    )
    return resultado
