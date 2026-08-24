"""Indicadores de rentabilidade de ciclos encerrados, agrupados por raça e
por lote de venda."""

from datetime import date, timedelta

from . import zootecnia
from .constantes import CARCASS_YIELD, KG_PER_ARROBA


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

        # A margem NÃO é limitada a 0..1: raça que deu prejuízo tem margem
        # negativa, e travá-la em zero faria prejuízo parecer empate. A spec
        # dizia "0..1" — o texto estava errado e foi corrigido junto com isto.
        margem = lucro_total / receita_total if receita_total > 0 else 0.0
        resultado.append({
            "raca": raca,
            "animais": animais,
            "lucro_por_cabeca": round(lucro_total / animais, 2),
            "lucro_por_arroba_produzida": (
                round(lucro_total / arrobas, 2) if arrobas > 0 else 0.0
            ),
            "gmd_medio": round(sum(gmds) / len(gmds), 3) if gmds else 0.0,
            "margem": round(margem, 4),
        })

    return sorted(
        resultado,
        key=lambda item: item["lucro_por_cabeca"],
        reverse=True,
    )


def por_lote_de_venda(vendas: list[dict]) -> list[dict]:
    """Custo por kg e por arroba de cada LOTE DE VENDA (ROADMAP §5, Trilha 3
    — o item que fechava a trilha: já existia por animal e por piquete).

    Um "lote de venda" é o grupo de linhas de `sales` que compartilham o
    mesmo `lot_ref` — gerado por `register_sale` sempre que a venda envolve
    mais de um animal, ou o modo de precificação é "lote" (ROADMAP §5:
    "resultado por lote fecha com a soma dos animais"). Venda de um único
    animal fora desses casos não tem `lot_ref` (é `None`) — cada uma dessas
    vendas vira seu próprio lote de 1 cabeça, nunca é misturada com outra
    venda avulsa só porque as duas têm `lot_ref` nulo.

    Peso e custo do lote são a SOMA das linhas que o compõem. O custo usa
    `cost_at_sale` — o custo do animal já CONGELADO no momento da venda —
    e não uma nova consulta ao custo atual do animal, que pode ter mudado
    desde então (a mesma razão pela qual a DRE usa `cost_at_sale`, não o
    custo acumulado corrente). A conversão para arroba usa o rendimento de
    carcaça MÉDIO dos animais do lote (mesmo critério de
    `app.py::_nutricao_custo_por_piquete` para o custo por piquete), caindo
    no padrão do rebanho quando a venda não carrega o dado (join vazio com
    `animals` — ex.: animal removido do cadastro depois de vendido).

    Peso total zero (dado ausente) devolve `custo_por_kg`/`custo_por_arroba`
    como `None` em vez de dividir por zero — indisponível, não zero.
    """
    grupos: dict[str, dict] = {}
    ordem: list[str] = []

    for venda in vendas:
        chave = venda.get("lot_ref") or f"__venda_{venda.get('id', id(venda))}__"
        grupo = grupos.get(chave)
        if grupo is None:
            grupo = {
                "lot_ref": venda.get("lot_ref"),
                "sale_date": venda.get("sale_date"),
                "animais": 0,
                "peso_total_kg": 0.0,
                "custo_total": 0.0,
                "receita_total": 0.0,
                "lucro_total": 0.0,
                "_yields": [],
            }
            grupos[chave] = grupo
            ordem.append(chave)

        grupo["animais"] += 1
        grupo["peso_total_kg"] += float(venda.get("weight_kg") or 0.0)
        grupo["custo_total"] += float(venda.get("cost_at_sale") or 0.0)
        grupo["receita_total"] += float(venda.get("total_value") or 0.0)
        grupo["lucro_total"] += float(venda.get("profit") or 0.0)
        grupo["_yields"].append(float(venda.get("carcass_yield") or CARCASS_YIELD))

    resultado = []
    for chave in ordem:
        grupo = grupos[chave]
        peso = grupo["peso_total_kg"]
        yield_medio = sum(grupo["_yields"]) / len(grupo["_yields"])
        arrobas = zootecnia.kg_to_arrobas(peso, yield_medio) if peso else 0.0

        resultado.append({
            "lot_ref": grupo["lot_ref"],
            "sale_date": grupo["sale_date"],
            "animais": grupo["animais"],
            "peso_total_kg": round(peso, 2),
            "custo_total": round(grupo["custo_total"], 2),
            "receita_total": round(grupo["receita_total"], 2),
            "lucro_total": round(grupo["lucro_total"], 2),
            "custo_por_kg": round(grupo["custo_total"] / peso, 2) if peso else None,
            "custo_por_arroba": (
                round(grupo["custo_total"] / arrobas, 2) if arrobas else None
            ),
        })

    return resultado
