"""Regras financeiras puras. Nada de banco aqui — quem lê é
`repositories/financeiro.py` (ROADMAP R1/R9).
"""


def valor_esperado_venda(peso_atual_kg: float, preco_por_kg: float) -> float:
    """Valor esperado de venda: peso atual × preço/kg da categoria.

    Anteriormente esta conta era feita em `repositories/financeiro.py::expected_sale_value`.
    Hoje, aqui fazemos apenas a conta e resolver o preço da categoria é
    trabalho do repositório, que é quem tem `_conn()`.
    """
    return round(peso_atual_kg * preco_por_kg, 2)
