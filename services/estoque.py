"""Módulo de serviços de estoque e custos de insumos."""


def custo_medio_ponderado(
    saldo_atual: float,
    custo_atual: float,
    quantidade_entrada: float,
    custo_entrada: float,
) -> float:
    """Novo custo unitário após uma entrada, ponderado pelas quantidades.

    (saldo_atual × custo_atual + quantidade_entrada × custo_entrada)
    ÷ (saldo_atual + quantidade_entrada)

    Arredondar para 2 casas.
    """
    if quantidade_entrada <= 0:
        return round(float(custo_atual), 2)

    if saldo_atual <= 0:
        return round(float(custo_entrada), 2)

    total_quantidade = float(saldo_atual) + float(quantidade_entrada)
    custo_total = (float(saldo_atual) * float(custo_atual)) + (
        float(quantidade_entrada) * float(custo_entrada)
    )

    return round(custo_total / total_quantidade, 2)
