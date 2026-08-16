"""Centros de custo (Trilha 3, ROADMAP §5) — o piquete como unidade de custo.

Junta custo fixo alocado a um piquete (`fixed_costs.lote_id`) com custo por
animal (`animal_costs`, agregado pelo piquete atual do animal) num único
retrato por centro de custo. Nenhuma consulta nova aqui — os dois totais já
vêm prontos de `repositories/financeiro.py`; isto é só a forma certa de
juntá-los.
"""


def consolidar(fixos_por_lote: dict, animal_por_lote: dict,
               cabecas_por_lote: dict, nomes_lotes: dict) -> list[dict]:
    """Combina os dois totais por centro de custo, do maior para o menor.

    `lote_id=None` em `fixos_por_lote` vira o centro **"Geral da Fazenda"**
    — custo fixo que não foi alocado a um piquete específico (salário do
    gerente, contabilidade). `animal_por_lote` nunca tem chave `None`: todo
    animal ativo pertence a algum piquete.
    """
    centros = set(fixos_por_lote) | set(animal_por_lote)
    linhas = []
    for lote_id in centros:
        fixos = round(float(fixos_por_lote.get(lote_id, 0.0)), 2)
        animal = round(float(animal_por_lote.get(lote_id, 0.0)), 2)
        nome = "Geral da Fazenda" if lote_id is None else nomes_lotes.get(lote_id, lote_id)
        linhas.append({
            "lote_id": lote_id,
            "nome": nome,
            "cabecas": cabecas_por_lote.get(lote_id, 0),
            "custos_fixos": fixos,
            "custos_animal": animal,
            "total": round(fixos + animal, 2),
        })

    linhas.sort(key=lambda l: (-l["total"], l["nome"]))
    return linhas
