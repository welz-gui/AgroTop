"""Máquina de estados pura para o ciclo de vida regulatório do animal."""


_ESTADOS = (
    "ativo",
    "carencia",
    "vendido",
    "morto",
    "rascunho",
    "ativo_sem_identificacao_oficial",
    "identificado_oficialmente",
    "identificacao_pendente_sincronizacao",
    "identificacao_rejeitada",
    "movimentacao_programada",
    "em_transito",
    "transferido",
    "abatido",
    "desaparecido",
    "furtado",
    "baixado_por_ajuste",
    "cadastro_bloqueado",
)

_ESTADOS_FINAIS = frozenset({
    "vendido",
    "morto",
    "transferido",
    "abatido",
    "baixado_por_ajuste",
})

_TRANSICOES = {
    estado: {
        destino: "autorizacao" if estado in _ESTADOS_FINAIS else "livre"
        for destino in _ESTADOS
        if destino != "rascunho"
    }
    for estado in _ESTADOS
}


def _resultado(
    permitida: bool,
    *,
    exige_autorizacao: bool = False,
    exige_justificativa: bool = False,
    motivo: str = "",
) -> dict:
    return {
        "permitida": permitida,
        "exige_autorizacao": exige_autorizacao,
        "exige_justificativa": exige_justificativa,
        "motivo": motivo,
    }


def _motivo_autorizacao(estado_atual: str, estado_novo: str) -> str:
    if estado_novo == "ativo" and estado_atual in {"morto", "abatido", "vendido"}:
        return (
            f"Animal {estado_atual} só volta a ativo com autorização de administrador "
            "e justificativa registrada."
        )
    return (
        f"Animal em estado {estado_atual} só pode mudar para {estado_novo} com "
        "autorização de administrador e justificativa registrada."
    )


def transicao_permitida(
    estado_atual: str,
    estado_novo: str,
    *,
    tem_autorizacao: bool = False,
) -> dict:
    """Avalia se a mudança de estado do animal é permitida.

    `tem_autorizacao`: o usuário possui a permissão específica exigida para
    transições sensíveis (§14.2). Injetado — a função não consulta permissões.

    Retorna:
        {
          "permitida": bool,
          "exige_autorizacao": bool,
          "exige_justificativa": bool,
          "motivo": str,
        }
    """
    if estado_atual not in _TRANSICOES:
        return _resultado(False, motivo=f"Estado atual inválido: '{estado_atual}'.")
    if estado_novo not in _TRANSICOES:
        return _resultado(False, motivo=f"Estado novo inválido: '{estado_novo}'.")
    if estado_atual == estado_novo:
        return _resultado(True)

    politica = _TRANSICOES[estado_atual].get(estado_novo)
    if politica is None:
        return _resultado(
            False,
            motivo="Rascunho é um estado inicial e não pode ser destino de uma transição.",
        )
    if politica == "livre":
        return _resultado(True)

    if tem_autorizacao:
        return _resultado(
            True,
            exige_autorizacao=True,
            exige_justificativa=True,
            motivo="Transição sensível autorizada; registre a justificativa obrigatória.",
        )
    return _resultado(
        False,
        exige_autorizacao=True,
        exige_justificativa=True,
        motivo=_motivo_autorizacao(estado_atual, estado_novo),
    )


def estados() -> list[str]:
    """Lista dos estados válidos, na ordem em que devem aparecer na interface."""
    return list(_ESTADOS)


def estados_finais() -> set[str]:
    """Estados dos quais só se sai com autorização (morto, abatido, vendido…)."""
    return set(_ESTADOS_FINAIS)
