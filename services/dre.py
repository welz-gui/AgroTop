"""DRE gerencial — Demonstração do Resultado do Exercício (Trilha 3, ROADMAP §5).

Reorganiza o resumo financeiro do período (`repositories.financeiro.
get_financial_summary`) na estrutura de uma DRE: Receita Bruta, CPV, Lucro
Bruto, Despesas Operacionais, Resultado Operacional, Resultado Líquido.

Nenhuma consulta nova: os números já existem em `get_financial_summary`.
Isto é só a forma certa de somá-los — ver `montar_dre` para o porquê.
"""


def montar_dre(resumo: dict) -> dict:
    """Monta a DRE a partir do dicionário de `get_financial_summary`.

    A diferença de fundo para o "Resultado (Caixa)" já existente na tela: o
    CPV (Custo dos Animais Vendidos) usa o custo ACUMULADO do animal na hora
    da venda (`sales.cost_at_sale` — compra + custos operacionais lançados
    até ali), não o que foi gasto comprando ou mantendo animais no período.

    Um bezerro comprado em janeiro e ainda no pasto em dezembro não vira
    despesa da DRE de dezembro: o dinheiro saiu, mas o valor continua no
    rebanho — é patrimônio, não custo do período (o mesmo raciocínio de
    estoque de uma indústria). Só quando ele é vendido (ou morre) o custo
    acumulado "sai do estoque" e vira resultado. É o princípio contábil de
    competência: casar receita e custo no mesmo lançamento, não no mesmo
    caixa.

    Por isso `resumo["compra_animais"]` e `resumo["operacional"]` (custo
    fixo por animal, cost_type='operacional') **não entram na DRE** — o que
    foi incorrido em animais já vendidos está dentro de `cost_at_sale`
    (então já está no CPV); o que foi incorrido em animais ainda ativos
    continua capitalizado no rebanho. Somar de novo aqui contaria duas vezes
    o que já está no CPV, ou anteciparia despesa de um animal que ainda nem
    foi vendido.

    Medicamentos e Nutrição/Trato continuam como Despesas Operacionais: o
    schema atual não aloca esses custos por animal (ficam em
    `insumo_transactions`, nunca em `animal_costs`), então não têm como
    entrar no CPV — tratá-los como despesa do período é a leitura correta
    possível hoje. Alocar por animal fica para quando essa coluna existir
    (mesma nota que `previsao_estoque` já registra sobre `prazo_reposicao_dias`).
    """
    receita_bruta = round(float(resumo.get("receita_total", 0.0)), 2)
    lucro_bruto = round(
        sum(v.get("lucro", 0.0) for v in resumo.get("vendas", {}).values()), 2)
    cpv = round(receita_bruta - lucro_bruto, 2)

    despesas_operacionais = {
        "Medicamentos": round(float(resumo.get("medicamentos", 0.0)), 2),
        "Nutrição/Trato": round(float(resumo.get("nutricao", 0.0)), 2),
        "Custos Fixos": round(float(resumo.get("custos_fixos", 0.0)), 2),
    }
    total_despesas_operacionais = round(sum(despesas_operacionais.values()), 2)
    resultado_operacional = round(lucro_bruto - total_despesas_operacionais, 2)

    perda_mortalidade = round(float(resumo.get("perda_mortalidade", 0.0)), 2)
    resultado_liquido = round(resultado_operacional - perda_mortalidade, 2)

    margem_bruta_pct = (round(lucro_bruto / receita_bruta * 100, 2)
                        if receita_bruta else None)
    margem_liquida_pct = (round(resultado_liquido / receita_bruta * 100, 2)
                          if receita_bruta else None)

    return {
        "receita_bruta": receita_bruta,
        "cpv": cpv,
        "lucro_bruto": lucro_bruto,
        "margem_bruta_pct": margem_bruta_pct,
        "despesas_operacionais": despesas_operacionais,
        "total_despesas_operacionais": total_despesas_operacionais,
        "resultado_operacional": resultado_operacional,
        "perda_mortalidade": perda_mortalidade,
        "resultado_liquido": resultado_liquido,
        "margem_liquida_pct": margem_liquida_pct,
    }
