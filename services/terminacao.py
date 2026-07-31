"""Simulador de terminação: pasto × semiconfinamento × confinamento.

Função pura. Ver ROADMAP.md R8 — esta regra chegou a existir em três cópias
(database.py, backend_api e o app Flutter abandonado). Uma só, aqui.
"""

from .constantes import CARCASS_YIELD, KG_PER_ARROBA


# Cenários-padrão editáveis (o usuário calibra na tela e salva em settings).
TERMINACAO_DEFAULTS = [
    {"nome": "Pasto",            "gmd": 0.500, "custo_dia":  3.50, "rendimento": 0.50},
    {"nome": "Semiconfinamento", "gmd": 0.900, "custo_dia":  8.00, "rendimento": 0.53},
    {"nome": "Confinamento",     "gmd": 1.350, "custo_dia": 14.00, "rendimento": 0.55},
]


def simular_terminacao(peso_atual: float, peso_meta: float, preco_arroba: float,
                       cenarios: list[dict], custo_boi_magro: float = 0.0) -> list[dict]:
    """Compara a viabilidade econômica de terminar o boi por estratégia.

    peso_atual/peso_meta em kg; preco_arroba = R$ por @ do boi gordo (venda).
    Cada cenário: {'nome', 'gmd' (kg/dia), 'custo_dia' (R$/cab/dia), 'rendimento' (fração)}.
    custo_boi_magro: custo/valor de aquisição do animal hoje (R$, igual p/ todos;
      opcional — se 0, o lucro reflete só a etapa de terminação).

    Retorna, por cenário (mais lucrativo primeiro): dias, ganho_kg, arrobas_produzidas,
    custo_alimentar, receita, lucro, lucro_por_dia, custo_por_arroba, margem, viavel.
    """
    ganho_kg = round(peso_meta - peso_atual, 1)
    out = []
    for c in cenarios:
        gmd  = float(c.get("gmd") or 0)
        cd   = float(c.get("custo_dia") or 0)
        rend = float(c.get("rendimento") or CARCASS_YIELD)
        if ganho_kg <= 0 or gmd <= 0:
            dias = None
            custo_alim = arrobas_prod = receita = lucro = None
            lpd = cpa = margem = None
            viavel = False
        else:
            dias = int(round(ganho_kg / gmd))
            custo_alim   = round(dias * cd, 2)
            arrobas_prod = round(ganho_kg * rend / KG_PER_ARROBA, 2)
            receita      = round(peso_meta * rend / KG_PER_ARROBA * preco_arroba, 2)
            lucro        = round(receita - custo_alim - custo_boi_magro, 2)
            lpd    = round(lucro / dias, 2) if dias else None
            cpa    = round(custo_alim / arrobas_prod, 2) if arrobas_prod > 0 else None
            margem = round(lucro / receita * 100, 1) if receita > 0 else None
            viavel = lucro > 0
        out.append({
            "nome": c.get("nome", "—"), "gmd": round(gmd, 3), "custo_dia": round(cd, 2),
            "rendimento": round(rend, 3), "dias": dias, "ganho_kg": ganho_kg,
            "arrobas_produzidas": arrobas_prod, "custo_alimentar": custo_alim,
            "receita": receita, "lucro": lucro, "lucro_por_dia": lpd,
            "custo_por_arroba": cpa, "margem": margem, "viavel": viavel,
        })
    # ordena: viáveis primeiro, maior lucro primeiro; inválidos ao final
    return sorted(out, key=lambda x: (x["lucro"] is None, -(x["lucro"] or 0)))
