"""Monta os indicadores de conformidade a partir do rebanho em memória."""

from datetime import date


_STATUS_ATIVO = "ativo"
_MOVIMENTACOES_ABERTAS = frozenset(("rascunho", "liberada", "em_transito"))


def _data_anterior(data_prevista: object, referencia: str) -> bool:
    """Retorna se uma data ISO válida está antes da data de referência."""

    if not isinstance(data_prevista, str) or not data_prevista:
        return False
    try:
        return date.fromisoformat(data_prevista) < date.fromisoformat(referencia)
    except ValueError:
        return False


def montar_rebanho(
    *,
    animais: list[dict],
    identificadores_ativos: list[dict],
    dispositivos: list[dict],
    eventos_pendentes: int,
    movimentacoes_abertas: list[dict],
    referencia: str,
) -> dict:
    """Traduz os registros do rebanho para o contrato de conformidade."""

    ativos = [animal for animal in animais if animal.get("status") == _STATUS_ATIVO]
    uuids_ativos = {animal.get("uuid") for animal in ativos}

    identificados_oficial = {
        item.get("animal_uuid")
        for item in identificadores_ativos
        if item.get("animal_uuid") in uuids_ativos
        and item.get("tipo") == "oficial_pnib"
    }
    identificados_manejo = {
        item.get("animal_uuid")
        for item in identificadores_ativos
        if item.get("animal_uuid") in uuids_ativos and item.get("tipo") == "manejo"
    }

    return {
        "animais_ativos": len(ativos),
        "com_identificacao_oficial": len(identificados_oficial),
        "com_identificacao_manejo": len(identificados_manejo),
        "com_propriedade": sum(1 for animal in ativos if animal.get("property_id")),
        "nascidos_sem_mae": sum(
            1
            for animal in ativos
            if animal.get("origem") == "nascido" and not animal.get("mae_uuid")
        ),
        "eventos_pendentes_sincronizacao": eventos_pendentes,
        "com_nascimento_estimado": sum(
            1 for animal in ativos if animal.get("birth_estimated")
        ),
        "dispositivos_com_divergencia": sum(
            1
            for dispositivo in dispositivos
            if dispositivo.get("animal_uuid") in uuids_ativos
            and dispositivo.get("divergencia") is not None
        ),
        "movimentacoes_abertas_vencidas": sum(
            1
            for movimentacao in movimentacoes_abertas
            if movimentacao.get("status") in _MOVIMENTACOES_ABERTAS
            and _data_anterior(movimentacao.get("data_prevista"), referencia)
        ),
    }
