"""Indicadores mensais de completude dos dados operacionais."""

import calendar
from datetime import date, timedelta


_MINIMOS = {
    "animais_com_pesagem_em_dia": 0.80,
    "intervalos_uteis_gmd": 0.70,
    "contexto_da_pesagem": 0.95,
    "execucao_nutricional": 0.90,
    "cobertura_ambiental": 0.90,
}

_MENSAGENS = {
    "animais_com_pesagem_em_dia": (
        "Pese os animais sem registro nos últimos 60 dias."
    ),
    "intervalos_uteis_gmd": (
        "Repita as pesagens em intervalos de 30 a 60 dias para calcular o GMD."
    ),
    "contexto_da_pesagem": (
        "Preencha o lote e o método em todas as pesagens."
    ),
    "execucao_nutricional": (
        "Registre a execução dos dias-lote planejados."
    ),
    "cobertura_ambiental": (
        "Registre a chuva em todas as semanas do mês."
    ),
}


def _data(valor: object) -> date | None:
    try:
        return date.fromisoformat(str(valor))
    except (TypeError, ValueError):
        return None


def _proporcao(parte: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return min(1.0, max(0.0, parte / total))


def _preenchido(valor: object) -> bool:
    if isinstance(valor, str):
        return bool(valor.strip())
    return valor is not None


def _animais_com_intervalo_util(pesagens: list[dict]) -> set[object]:
    datas_por_animal: dict[object, set[date]] = {}
    for pesagem in pesagens:
        animal_id = pesagem.get("animal_id")
        data_pesagem = _data(pesagem.get("data"))
        if animal_id is not None and data_pesagem is not None:
            datas_por_animal.setdefault(animal_id, set()).add(data_pesagem)

    animais: set[object] = set()
    for animal_id, datas in datas_por_animal.items():
        ordenadas = sorted(datas)
        if any(
            30 <= (atual - anterior).days <= 60
            for indice, atual in enumerate(ordenadas)
            for anterior in ordenadas[:indice]
        ):
            animais.add(animal_id)
    return animais


def avaliar_mes(
    ano: int,
    mes: int,
    animais_ativos: int,
    pesagens: list[dict],
    dias_lote_planejados: int,
    dias_lote_executados: int,
    semanas_com_chuva: int,
    semanas_no_mes: int,
) -> dict:
    """Indicadores de completude de um mês. Nada de banco aqui — tudo injetado.

    Meses sem dados retornam zero para os indicadores sem denominador. Assim, a
    ausência de coleta não é apresentada como mês completo e gera alertas para a
    operação.
    """
    ultimo_dia = date(ano, mes, calendar.monthrange(ano, mes)[1])
    inicio_janela = ultimo_dia - timedelta(days=60)

    animais_em_dia = {
        pesagem.get("animal_id")
        for pesagem in pesagens
        if pesagem.get("animal_id") is not None
        and (data_pesagem := _data(pesagem.get("data"))) is not None
        and inicio_janela <= data_pesagem <= ultimo_dia
    }
    animais_intervalo_util = _animais_com_intervalo_util(pesagens)
    pesagens_com_contexto = sum(
        _preenchido(pesagem.get("lote_id"))
        and _preenchido(pesagem.get("method"))
        for pesagem in pesagens
    )

    indicadores = {
        "animais_com_pesagem_em_dia": _proporcao(
            len(animais_em_dia), animais_ativos
        ),
        "intervalos_uteis_gmd": _proporcao(
            len(animais_intervalo_util), animais_ativos
        ),
        "contexto_da_pesagem": _proporcao(
            pesagens_com_contexto, len(pesagens)
        ),
        "execucao_nutricional": _proporcao(
            dias_lote_executados, dias_lote_planejados
        ),
        "cobertura_ambiental": _proporcao(
            semanas_com_chuva, semanas_no_mes
        ),
    }

    alertas = [
        {
            "indicador": indicador,
            "valor": valor,
            "minimo": _MINIMOS[indicador],
            "mensagem": _MENSAGENS[indicador],
        }
        for indicador, valor in indicadores.items()
        if valor < _MINIMOS[indicador]
    ]
    return {**indicadores, "alertas": alertas}
