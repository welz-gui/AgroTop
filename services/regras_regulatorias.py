"""Motor de regras regulatórias (PNIB §11).

O §11 abre com a exigência que define este módulo: **"as regras não devem ficar
fixadas no código-fonte"**. A portaria muda, cada UF acrescenta a sua, e um
frigorífico impõe protocolo próprio — codificar isso em `if` significa alterar o
sistema a cada mudança normativa.

Aqui as regras são **dados**: vêm de uma tabela, têm vigência, e este módulo só
as avalia. Regra nova não exige deploy.

## Vigência é a parte que se esquece

A regra que vale em 2027 não é a que vale em 2030 — o próprio PNIB tem prazos
escalonados, com identificação obrigatória para trânsito só a partir de
**01/01/2033**. Avaliar sempre pela regra de hoje reescreveria o passado: uma
movimentação de 2027 seria julgada por norma que ainda não existia.

Por isso `avaliar` recebe a **data de referência**, e não assume hoje.

Função pura: nada aqui consulta banco.
"""

from datetime import date, datetime
from typing import Any, Optional

ESFERAS = ("federal", "estadual", "protocolo", "interna")
NIVEIS = ("informativo", "alerta", "bloqueio")

# Operadores da condição. Deliberadamente poucos: condição é dado vindo de
# tabela, e um avaliador de expressão arbitrária seria porta de execução remota.
OPERADORES = ("igual", "diferente", "maior", "maior_igual", "menor",
              "menor_igual", "em", "nao_em", "vazio", "preenchido")


def _data(valor) -> Optional[date]:
    if isinstance(valor, date):
        return valor
    try:
        return datetime.strptime(str(valor), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def vigente_em(regra: dict, referencia: date) -> bool:
    """A regra estava em vigor nessa data?

    `data_inicial` ausente = sempre valeu; `data_final` ausente = ainda vale.
    """
    ini = _data(regra.get("data_inicial"))
    fim = _data(regra.get("data_final"))
    if ini and referencia < ini:
        return False
    if fim and referencia > fim:
        return False
    return True


def _bate_escopo(regra: dict, contexto: dict) -> bool:
    """A regra se aplica a este animal/operação?

    Campo vazio na regra significa **"qualquer"**, não "nenhum" — é o que
    permite escrever uma regra federal sem enumerar as 27 UFs.
    """
    for campo in ("uf", "especie", "categoria", "sexo", "finalidade",
                  "evento_aplicacao"):
        esperado = regra.get(campo)
        if esperado in (None, "", "*"):
            continue
        if str(contexto.get(campo, "")).lower() != str(esperado).lower():
            return False

    idade = contexto.get("idade_meses")
    if idade is not None:
        minima, maxima = regra.get("idade_min_meses"), regra.get("idade_max_meses")
        if minima is not None and idade < minima:
            return False
        if maxima is not None and idade > maxima:
            return False
    return True


def _comparar(operador: str, valor: Any, esperado: Any) -> bool:
    if operador == "vazio":
        return valor in (None, "", [], {})
    if operador == "preenchido":
        return valor not in (None, "", [], {})
    if operador == "em":
        return valor in (esperado or [])
    if operador == "nao_em":
        return valor not in (esperado or [])
    if operador == "igual":
        return valor == esperado
    if operador == "diferente":
        return valor != esperado

    # Comparações de ordem exigem números — comparar texto com `>` produziria
    # resultado por ordem alfabética, que ninguém espera de uma regra.
    try:
        v, e = float(valor), float(esperado)
    except (TypeError, ValueError):
        return False
    return {"maior": v > e, "maior_igual": v >= e,
            "menor": v < e, "menor_igual": v <= e}[operador]


def _condicao_dispara(condicao: Optional[dict], contexto: dict) -> bool:
    """A condição da regra foi satisfeita?

    `condicao` é `{"campo": str, "operador": str, "valor": Any}` ou uma lista
    delas — todas precisam bater (E lógico). Condição ausente = a regra dispara
    sempre que o escopo bater.
    """
    if not condicao:
        return True
    itens = condicao if isinstance(condicao, list) else [condicao]
    for c in itens:
        op = c.get("operador")
        if op not in OPERADORES:
            return False           # operador desconhecido nunca dispara
        if not _comparar(op, contexto.get(c.get("campo")), c.get("valor")):
            return False
    return True


def avaliar(regras: list[dict], contexto: dict,
            referencia: Optional[str] = None) -> list[dict]:
    """Aplica as regras vigentes ao contexto. Devolve as que dispararam.

    `regras`: linhas da tabela de regras, cada uma com nome, esfera, nível,
    vigência, escopo e condição.
    `contexto`: o que se sabe do animal/operação — uf, especie, categoria, sexo,
    finalidade, evento_aplicacao, idade_meses, e os campos que as condições citam.
    `referencia`: data pela qual julgar. **Omitir usa hoje**, o que só é correto
    para decisão presente — para reavaliar o passado, passe a data do fato.

    Retorna, ordenado por gravidade (bloqueio primeiro):
        [{"regra", "nivel", "esfera", "mensagem", "fundamento",
          "documentacao_exigida", "versao"}, ...]
    """
    ref = _data(referencia) or date.today()
    disparadas = []

    for r in regras:
        if not vigente_em(r, ref):
            continue
        if str(r.get("ativa", 1)) in ("0", "False", "false"):
            continue
        if not _bate_escopo(r, contexto):
            continue
        if not _condicao_dispara(r.get("condicao"), contexto):
            continue

        nivel = r.get("nivel") if r.get("nivel") in NIVEIS else "informativo"
        disparadas.append({
            "regra": r.get("nome"),
            "nivel": nivel,
            "esfera": r.get("esfera"),
            "mensagem": r.get("mensagem") or r.get("descricao") or r.get("nome"),
            "fundamento": r.get("fundamento"),
            "documentacao_exigida": r.get("documentacao_exigida"),
            "versao": r.get("versao"),
        })

    ordem = {"bloqueio": 0, "alerta": 1, "informativo": 2}
    return sorted(disparadas, key=lambda d: ordem.get(d["nivel"], 9))


def pode_prosseguir(disparadas: list[dict]) -> bool:
    return not any(d["nivel"] == "bloqueio" for d in disparadas)


def exige_confirmacao(disparadas: list[dict]) -> bool:
    return any(d["nivel"] == "alerta" for d in disparadas)


def simular(regra: dict, casos: list[dict],
            referencia: Optional[str] = None) -> dict:
    """§11.3: testa UMA regra contra vários casos **antes de ativá-la**.

    Existe porque ativar regra de bloqueio sem simular é descobrir o alcance
    dela no dia em que o caminhão está no curral. Responde quantos casos ela
    atinge e quais.
    """
    ref = _data(referencia) or date.today()
    atingidos = []
    for caso in casos:
        if not vigente_em(regra, ref):
            break
        if _bate_escopo(regra, caso) and _condicao_dispara(regra.get("condicao"), caso):
            atingidos.append(caso.get("id") or caso.get("animal_id"))

    return {
        "regra": regra.get("nome"),
        "nivel": regra.get("nivel"),
        "vigente_na_data": vigente_em(regra, ref),
        "total_avaliado": len(casos),
        "atingidos": len(atingidos),
        "ids": atingidos,
        "percentual": round(len(atingidos) / len(casos) * 100, 1) if casos else 0.0,
    }
