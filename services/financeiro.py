"""Regras financeiras puras. Nada de banco aqui — quem lê é
`repositories/financeiro.py` (ROADMAP R1/R9).
"""


def valor_esperado_venda(peso_atual_kg: float, preco_por_kg: float) -> float:
    """Valor esperado de venda: peso atual × preço/kg da categoria.

    Chegou aqui vindo de `repositories/financeiro.py::expected_sale_value`, que
    até 2026-08-06 fazia a conta misturada com a consulta ao preço — a mesma
    função lia `category_prices` **e** calculava, então "regra de negócio" e
    "camada de dados" eram a mesma linha. Aqui só a conta: os dois números já
    chegam resolvidos, e resolver o preço continua sendo trabalho do
    repositório, que é quem tem `_conn()`.
    """
    return round(peso_atual_kg * preco_por_kg, 2)
