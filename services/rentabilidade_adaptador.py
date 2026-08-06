"""Monta ciclos encerrados para os indicadores de rentabilidade."""

from datetime import date


def montar_ciclos(
    vendas: list[dict],
    animais_por_uuid: dict[str, dict],
    custo_total_por_uuid: dict[str, float],
) -> list[dict]:
    """Converte cada venda com animal conhecido em um ciclo de rentabilidade.

    O peso de saída usa ``current_weight`` do cadastro como proxy do peso no
    momento da venda, pois o sistema ainda não guarda peso histórico por venda.
    Um fluxo correto não deve pesar novamente um animal depois de vendido; se
    isso ocorrer, o ciclo refletirá a limitação da fonte disponível.
    """

    ciclos: list[dict] = []
    for venda in vendas:
        animal_uuid = venda["animal_uuid"]
        animal = animais_por_uuid.get(animal_uuid)
        if animal is None:
            continue

        dias = max(
            0,
            (
                date.fromisoformat(venda["sale_date"])
                - date.fromisoformat(animal["entry_date"])
            ).days,
        )
        ciclos.append(
            {
                "raca": animal["breed"],
                "peso_entrada": float(animal["entry_weight"]),
                "peso_saida": float(animal["current_weight"]),
                "custo_total": float(custo_total_por_uuid.get(animal_uuid, 0.0)),
                "receita": float(venda["total_value"]),
                "dias": dias,
            }
        )

    return ciclos
