"""Dados do produto aplicado num tratamento: princípio ativo, lote e validade.

Para o tratamento deixar trilha defensável, a aplicação precisa dizer **o que**
foi aplicado (princípio ativo), **de qual lote** e **até quando valia**. Os três
são opcionais (o campo pode não ter a embalagem à mão, e registros antigos não
têm), mas quando a validade vem, ela precisa cobrir a data da aplicação: produto
vencido não se aplica.

Funções puras: sem banco, sem Streamlit.
"""

from datetime import datetime

LIMITE_PRINCIPIO_ATIVO = 120
LIMITE_LOTE = 60


class TratamentoInvalido(ValueError):
    """Dado do produto aplicado inválido (ex.: produto vencido). Nada é gravado."""


def _texto(valor, limite: int, rotulo: str) -> str:
    # Tira as pontas e colapsa espaços repetidos: "  Ivermectina   1%" == "Ivermectina 1%".
    t = " ".join(str(valor or "").split())
    if len(t) > limite:
        raise TratamentoInvalido(f"{rotulo} muito longo (máximo {limite} caracteres).")
    return t


def _data_iso(valor, rotulo: str) -> str:
    v = str(valor or "").strip()
    if not v:
        return ""
    try:
        d = datetime.strptime(v, "%Y-%m-%d").date()
    except ValueError:
        raise TratamentoInvalido(f"{rotulo} inválida: use o formato AAAA-MM-DD.") from None
    return d.isoformat()


def normalizar_produto(principio_ativo, lote, validade, data_aplicacao) -> dict:
    """Valida e normaliza os dados do produto aplicado.

    Devolve `{"principio_ativo", "lote_produto", "validade_produto"}` (texto, vazio
    quando não informado). Levanta `TratamentoInvalido` se a validade não é uma data
    AAAA-MM-DD ou é anterior à data da aplicação (vence no próprio dia: ainda vale).
    """
    out = {
        "principio_ativo": _texto(principio_ativo, LIMITE_PRINCIPIO_ATIVO, "Princípio ativo"),
        "lote_produto": _texto(lote, LIMITE_LOTE, "Lote"),
        "validade_produto": _data_iso(validade, "Validade"),
    }
    if out["validade_produto"]:
        try:
            aplicada = datetime.strptime(str(data_aplicacao), "%Y-%m-%d").date().isoformat()
        except ValueError:
            aplicada = ""      # data da aplicação ilegível: outra regra cuida disso
        if aplicada and out["validade_produto"] < aplicada:
            raise TratamentoInvalido(
                f"Produto vencido em {out['validade_produto']}: não pode ser aplicado "
                f"em {aplicada}.")
    return out
