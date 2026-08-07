"""Adapta leituras e janelas operacionais para os indicadores mensais."""

import calendar
from datetime import date, timedelta


def normalizar_pesagens(pesagens_brutas: list[dict]) -> list[dict]:
    """Renomeia os campos de ``weighings`` para o contrato de ``avaliar_mes``."""

    return [
        {
            "animal_id": pesagem.get("animal_uuid"),
            "data": pesagem.get("weigh_date"),
            "lote_id": pesagem.get("lote_id"),
            "method": pesagem.get("method"),
        }
        for pesagem in pesagens_brutas
    ]


def janela_do_mes(
    ano: int,
    mes: int,
    *,
    checagens_de_trato: list[dict],
    leituras_de_chuva: list[dict],
) -> dict:
    """Calcula os denominadores e numeradores operacionais do mês.

    As checagens recebidas são as linhas do mês retornadas pelo repositório.
    Leituras de chuva são filtradas pela data para que a semana ISO que cruza
    a borda de um mês seja agrupada corretamente sem importar leituras do mês
    vizinho.
    """

    primeiro_dia = date(ano, mes, 1)
    ultimo_dia = date(ano, mes, calendar.monthrange(ano, mes)[1])
    semanas_do_mes = {
        (dia.isocalendar().year, dia.isocalendar().week)
        for deslocamento in range((ultimo_dia - primeiro_dia).days + 1)
        for dia in (primeiro_dia + timedelta(days=deslocamento),)
    }

    semanas_com_chuva: set[tuple[int, int]] = set()
    for leitura in leituras_de_chuva:
        try:
            data_leitura = date.fromisoformat(str(leitura.get("read_date")))
            volume = float(leitura.get("rain_mm", 0))
        except (TypeError, ValueError):
            continue
        if data_leitura.year != ano or data_leitura.month != mes or volume <= 0:
            continue
        semana = data_leitura.isocalendar()
        semanas_com_chuva.add((semana.year, semana.week))

    return {
        "dias_lote_planejados": len(checagens_de_trato),
        "dias_lote_executados": sum(
            checagem.get("status") == "feito"
            for checagem in checagens_de_trato
        ),
        "semanas_com_chuva": len(semanas_com_chuva),
        "semanas_no_mes": len(semanas_do_mes),
    }
