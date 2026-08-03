"""Máquina de estados do dispositivo de identificação (PNIB §5.2).

Doze estados, e a diferença entre eles não é cosmética: um brinco `perdido` pode
voltar a `disponivel` depois de encontrado, mas um `inutilizado` não — inutilizar
é ato definitivo, e permitir a volta destruiria a garantia de que aquele número
não será reaplicado.

`bloqueado_orgao` é o único estado que o sistema **não pode desfazer sozinho**:
quem bloqueou foi o órgão oficial, e só ele libera.

Função pura: nada aqui consulta banco.
"""

# §5.2 — na ordem do ciclo de vida, não alfabética.
ESTADOS = (
    "solicitado", "recebido", "disponivel", "reservado", "aplicado",
    "perdido", "danificado", "substituido", "inutilizado", "devolvido",
    "cancelado", "bloqueado_orgao",
)

# Estados dos quais NÃO se sai por operação normal.
_TERMINAIS = frozenset({"inutilizado", "devolvido", "cancelado"})

# Transições permitidas. O que não está aqui é recusado — lista de permissão,
# não de proibição: estado novo entra explicitamente, e não por esquecimento.
_PERMITIDAS = {
    "solicitado":     {"recebido", "cancelado"},
    "recebido":       {"disponivel", "danificado", "devolvido", "cancelado"},
    "disponivel":     {"reservado", "aplicado", "danificado", "perdido",
                       "inutilizado", "devolvido", "bloqueado_orgao"},
    "reservado":      {"aplicado", "disponivel", "perdido", "danificado",
                       "inutilizado"},
    "aplicado":       {"perdido", "danificado", "substituido", "inutilizado"},
    "perdido":        {"disponivel", "aplicado", "inutilizado"},
    "danificado":     {"substituido", "inutilizado", "devolvido"},
    "substituido":    {"inutilizado", "devolvido"},
    "inutilizado":    set(),
    "devolvido":      set(),
    "cancelado":      set(),
    "bloqueado_orgao": {"disponivel"},   # só com liberação do órgão
}

# Transições que exigem motivo registrado. Sem ele, ninguém reconstrói depois
# por que um brinco pago virou refugo.
_EXIGEM_MOTIVO = frozenset({"inutilizado", "perdido", "danificado",
                            "cancelado", "devolvido", "bloqueado_orgao"})


def _resultado(permitida: bool, *, exige_motivo: bool = False,
               exige_autorizacao: bool = False, motivo: str = "") -> dict:
    return {"permitida": permitida, "exige_motivo": exige_motivo,
            "exige_autorizacao": exige_autorizacao, "motivo": motivo}


def transicao_permitida(atual: str, novo: str, *,
                        tem_autorizacao: bool = False) -> dict:
    """Avalia a mudança de estado de um dispositivo.

    `tem_autorizacao` só importa para sair de `bloqueado_orgao` — é a permissão
    específica do §14.2, injetada: a função não consulta permissões.
    """
    if atual not in _PERMITIDAS:
        return _resultado(False, motivo=f"Estado atual inválido: '{atual}'.")
    if novo not in ESTADOS:
        return _resultado(False, motivo=f"Estado novo inválido: '{novo}'.")
    if atual == novo:
        return _resultado(True)

    if atual == "bloqueado_orgao" and not tem_autorizacao:
        return _resultado(
            False, exige_autorizacao=True,
            motivo="Dispositivo bloqueado pelo órgão oficial: só o órgão libera.")

    if novo not in _PERMITIDAS[atual]:
        if atual in _TERMINAIS:
            return _resultado(
                False,
                motivo=f"'{atual}' é estado definitivo e não admite mudança.")
        return _resultado(
            False, motivo=f"Transição de '{atual}' para '{novo}' não é prevista.")

    return _resultado(True, exige_motivo=novo in _EXIGEM_MOTIVO)


def estados() -> list[str]:
    """Estados na ordem do ciclo de vida — é a ordem em que a interface mostra."""
    return list(ESTADOS)


def terminais() -> set[str]:
    return set(_TERMINAIS)


def conferir_codigos(visual: str, eletronico: str, *,
                     digitos_comparados: int = 0) -> dict:
    """Confere se o código visual e o eletrônico são do mesmo dispositivo (§5.3).

    `digitos_comparados=0` compara os códigos inteiros, normalizados. Com N > 0,
    compara apenas os N últimos dígitos — é o que se faz quando o eletrônico
    carrega prefixo de país ou fabricante que o visual não mostra.

    Divergência entre os dois é **alerta, não bloqueio**: pode ser erro de
    leitura, e recusar a aplicação por isso trava o trabalho no curral.
    """
    def _norm(v):
        return "".join(c for c in str(v or "") if c.isalnum()).upper()

    v, e = _norm(visual), _norm(eletronico)
    if not v or not e:
        return {"confere": False, "divergencia": "codigo_ausente",
                "mensagem": "Código visual ou eletrônico não informado."}

    if digitos_comparados > 0:
        v_cmp, e_cmp = v[-digitos_comparados:], e[-digitos_comparados:]
    else:
        v_cmp, e_cmp = v, e

    if v_cmp == e_cmp:
        return {"confere": True, "divergencia": None, "mensagem": ""}
    return {"confere": False, "divergencia": "codigos_divergentes",
            "mensagem": f"Visual '{visual}' e eletrônico '{eletronico}' não conferem."}
