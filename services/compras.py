"""Compra de insumos: total da nota e parcelamento das contas a pagar.

Trilha 3 (Estoque → Financeiro): "compra gera conta a pagar" (ROADMAP §5).
Funções puras (ROADMAP R9) — quem grava compra, itens, estoque e contas a
pagar na mesma transação é `repositories/compras.py::registrar`.
"""

import calendar


def total_compra(itens: list[dict]) -> float:
    """Soma quantidade × custo_unitario de cada item da nota, em 2 casas.

    `itens`: lista de {"quantidade": float, "custo_unitario": float, ...} —
    outras chaves (ex.: `insumo_id`) são ignoradas aqui, de propósito: quem
    grava decide o que fazer com elas.
    """
    return round(
        sum(float(i["quantidade"]) * float(i["custo_unitario"]) for i in itens), 2
    )


def gerar_parcelas(valor_total: float, num_parcelas: int,
                   primeiro_vencimento: str) -> list[dict]:
    """Divide `valor_total` em `num_parcelas` mensais a partir de `primeiro_vencimento`.

    - **O resto do arredondamento vai inteiro para a última parcela** — dividir
      R$ 100,00 em 3 dá 33,33 + 33,33 + 33,34, nunca sobra nem falta centavo.
    - **Vencimento mensal, com o dia preso ao mês.** Comprar dia 31 e ter uma
      parcela caindo em fevereiro não pode gerar dia 31 inexistente: o dia é
      limitado ao último dia do mês de cada parcela (`calendar.monthrange`).

    `primeiro_vencimento`: data ISO (`AAAA-MM-DD`) da 1ª parcela.
    Retorna lista ordenada de
    `{"numero": int, "total": int, "valor": float, "vencimento": str}`.
    """
    if num_parcelas < 1:
        raise ValueError("num_parcelas deve ser >= 1")

    valor_total = round(float(valor_total), 2)
    base = round(valor_total / num_parcelas, 2)
    ano, mes, dia = (int(p) for p in primeiro_vencimento.split("-"))

    parcelas = []
    acumulado = 0.0
    for n in range(1, num_parcelas + 1):
        valor = base if n < num_parcelas else round(valor_total - acumulado, 2)
        acumulado = round(acumulado + valor, 2)

        m = mes + (n - 1)
        ano_p = ano + (m - 1) // 12
        mes_p = (m - 1) % 12 + 1
        ultimo_dia_do_mes = calendar.monthrange(ano_p, mes_p)[1]
        dia_p = min(dia, ultimo_dia_do_mes)

        parcelas.append({
            "numero": n,
            "total": num_parcelas,
            "valor": valor,
            "vencimento": f"{ano_p:04d}-{mes_p:02d}-{dia_p:02d}",
        })

    return parcelas
