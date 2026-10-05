"""Carência sanitária: até quando um animal não pode ser abatido (PNIB §8).

Função pura: quem lê o banco é a camada de dados; aqui só a conta.
"""

from datetime import date, timedelta


def fim_da_carencia(aplicacoes: list[dict], referencia: date) -> date | None:
    """Data em que termina a carência ainda vigente em `referencia`, ou None.

    Cada aplicação é `{"med_date": "AAAA-MM-DD", "withdrawal_days": int}`; o fim é
    `med_date + withdrawal_days`. Só contam aplicações feitas até `referencia`
    (uma venda lançada com data passada não é afetada por remédio dado depois)
    e cujo fim ainda não chegou. Entre várias, vale a mais longa.

    No dia do fim o animal já está liberado (`referencia < fim`): é o critério de
    `get_withdrawal_end`, que alimenta o status, a tela e a movimentação. O
    `carencia >= hoje` de `services/movimentacao.py` nunca enxerga esse dia, porque
    a data já chega filtrada por `get_withdrawal_end`.
    """
    fim = None
    for a in aplicacoes:
        dias = a.get("withdrawal_days")
        if not dias:
            continue
        try:
            aplicada = date.fromisoformat(str(a["med_date"]))
            termino = aplicada + timedelta(days=int(dias))
        except (KeyError, ValueError, TypeError):
            continue
        if aplicada <= referencia < termino and (fim is None or termino > fim):
            fim = termino
    return fim
