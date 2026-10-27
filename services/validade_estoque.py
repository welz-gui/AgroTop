"""Lote e validade do que está em estoque.

Duas coisas, ambas funções puras (sem banco, sem Streamlit):

1. validar o lote e a validade de uma ENTRADA de estoque;
2. descobrir DE QUAIS ENTRADAS é feito o saldo de hoje, para saber o que está vencido ou
   vencendo na prateleira.

O sistema guarda o saldo de cada insumo (`current_stock`) e cada movimento, mas não "o que
sobrou de cada lote". Então a divisão do saldo por lote é uma **estimativa**, com regra
explícita:

- consumo em que a aplicação informou o lote (`medications.lote_produto`) sai desse lote;
- o resto do consumo (trato, aplicação sem lote) sai por PEPS (primeiro que entra, primeiro
  que sai): primeiro do saldo anterior ao controle de lotes, depois da entrada mais antiga.

Se a prática for outra (usar o lote novo antes do velho sem anotar), o alerta pode não
enxergar um lote vencido que ainda está na prateleira. É por isso que registrar o lote na
aplicação importa: ele torna a conta exata.
"""

from datetime import date, datetime, timedelta

LIMITE_LOTE = 60
DIAS_ALERTA = 30
_EPS = 1e-9


class LoteInvalido(ValueError):
    """Lote ou validade de entrada inválidos (ex.: produto que já chegou vencido). Nada é gravado."""


def normalizar_lote_entrada(lote, validade, data_entrada) -> dict:
    """Valida e normaliza o lote e a validade de uma entrada de estoque.

    Devolve `{"lote_produto", "validade_produto"}` (texto, vazio quando não informado).
    Levanta `LoteInvalido` se o lote é longo demais, se a validade não é AAAA-MM-DD ou se
    é anterior à data de entrada (vence no próprio dia: ainda vale).
    """
    l = " ".join(str(lote or "").split())
    if len(l) > LIMITE_LOTE:
        raise LoteInvalido(f"Lote muito longo (máximo {LIMITE_LOTE} caracteres).")
    v = str(validade or "").strip()
    if v:
        try:
            dv = datetime.strptime(v, "%Y-%m-%d").date()
        except ValueError:
            raise LoteInvalido("Validade inválida: use o formato AAAA-MM-DD.") from None
        v = dv.isoformat()
        entrada = str(data_entrada or "")[:10]
        if entrada and v < entrada:
            raise LoteInvalido(f"O produto já chegou vencido: validade {v}, entrada em {entrada}.")
    return {"lote_produto": l, "validade_produto": v}


def situacao(validade, hoje, dias: int = DIAS_ALERTA) -> str:
    """'vencido', 'vencendo' (vence em até `dias` dias), 'ok' ou 'sem_validade'."""
    v = str(validade or "")[:10]
    if not v:
        return "sem_validade"
    h = hoje if isinstance(hoje, date) else date.fromisoformat(str(hoje)[:10])
    if v < h.isoformat():
        return "vencido"
    if v <= (h + timedelta(days=dias)).isoformat():
        return "vencendo"
    return "ok"


def lotes_do_insumo(entradas, saldo, saidas_liquidas, consumo_por_lote) -> list[dict]:
    """O que resta de cada entrada de um insumo.

    `entradas`: dicts `{"id", "data", "quantidade", "lote", "validade"}` na ordem de chegada
    (mais antiga primeiro). `saldo`: estoque atual. `saidas_liquidas`: soma de todas as saídas
    (as estornadas já entram líquidas). `consumo_por_lote`: `{lote: quantidade}` de aplicações
    que informaram o lote.

    Devolve `{"entrada_id", "data", "lote", "validade", "restante"}` só para o que ainda tem
    saldo; o saldo anterior ao controle de lotes (sem entrada que o explique) vem como uma
    linha sem lote e sem validade.
    """
    itens = [
        {"entrada_id": e.get("id"), "data": e.get("data"), "lote": e.get("lote") or None,
         "validade": e.get("validade") or None, "restante": float(e["quantidade"])}
        for e in entradas
    ]
    # 1) Consumo com lote informado sai desse lote, da entrada mais antiga dele.
    explicito = 0.0
    for lote, qtd in (consumo_por_lote or {}).items():
        falta = float(qtd)
        for it in itens:
            if falta <= _EPS:
                break
            if it["lote"] == lote and it["restante"] > _EPS:
                tira = min(it["restante"], falta)
                it["restante"] -= tira
                falta -= tira
                explicito += tira

    # 2) O saldo anterior ao controle de lotes é o que o saldo atual tem a mais que as entradas.
    total_entradas = sum(float(e["quantidade"]) for e in entradas)
    base = max(0.0, float(saldo) - total_entradas + float(saidas_liquidas))
    sem_lote = max(0.0, float(saidas_liquidas) - explicito)

    # 3) PEPS para o consumo sem lote: primeiro o saldo anterior, depois a entrada mais antiga.
    da_base = min(base, sem_lote)
    base -= da_base
    sem_lote -= da_base
    for it in itens:
        if sem_lote <= _EPS:
            break
        tira = min(it["restante"], sem_lote)
        it["restante"] -= tira
        sem_lote -= tira

    saida = [it for it in itens if it["restante"] > _EPS]
    if base > _EPS:
        saida.insert(0, {"entrada_id": None, "data": None, "lote": None,
                         "validade": None, "restante": base})
    return saida
