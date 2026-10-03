"""Indicador gerencial de dados do rebanho para o PNIB."""

from dataclasses import dataclass
from datetime import date

_PRAZO_IDENTIFICACAO = date(2033, 1, 1)
_AVISO = "Indicador de gestão; não substitui avaliação de conformidade legal."
_DIMENSOES = (
    {"nome": "Identificação oficial", "peso": 35.0},
    {"nome": "Propriedade definida", "peso": 15.0},
    {"nome": "Vínculo materno", "peso": 15.0},
    {"nome": "Sincronização em dia", "peso": 15.0},
    {"nome": "Nascimento com data exata", "peso": 10.0},
    {"nome": "Sem divergência de dispositivo", "peso": 10.0},
)


def dimensoes_avaliadas() -> list[dict]:
    """As dimensões e seus pesos, para a interface explicar o cálculo."""
    return [dict(dimensao) for dimensao in _DIMENSOES]


def _quantidade(rebanho: dict, campo: str) -> int:
    return max(0, int(rebanho.get(campo, 0)))


def _faltam(total: int, presentes: int) -> int:
    return max(0, total - min(total, presentes))


def _nota(total: int, faltam: int) -> float:
    if total == 0:
        return 100.0
    return round(100.0 * (1.0 - min(total, faltam) / total), 2)


def _frase(quantidade: int, singular: str, plural: str) -> str:
    unidade = singular if quantidade == 1 else plural
    return f"{quantidade} {unidade}."


def _dimensao(
    definicao: dict,
    total: int,
    faltam: int,
    mensagem: str,
    *,
    nota: float | None = None,
) -> dict:
    return {
        "nome": definicao["nome"],
        "peso": definicao["peso"],
        "nota": _nota(total, faltam) if nota is None else nota,
        "faltam": faltam,
        "mensagem": f"{mensagem} {_AVISO}",
    }


def _faixa(escore: float) -> str:
    if escore >= 100.0:
        return "completo"
    if escore >= 85.0:
        return "bom"
    if escore >= 70.0:
        return "atencao"
    return "critico"


@dataclass
class _IndicadoresRebanho:
    faltantes: tuple[int, ...]
    mensagens: list[str]
    sem_manejo: int
    movimentacoes_vencidas: int


def _extrair_indicadores(
    rebanho: dict, total: int, antes_do_prazo: bool
) -> _IndicadoresRebanho:
    if total == 0:
        return _IndicadoresRebanho(
            faltantes=(0, 0, 0, 0, 0, 0),
            mensagens=["Sem animais ativos para avaliar."] * 6,
            sem_manejo=0,
            movimentacoes_vencidas=0,
        )

    sem_oficial = _faltam(total, _quantidade(rebanho, "com_identificacao_oficial"))
    sem_propriedade = _faltam(total, _quantidade(rebanho, "com_propriedade"))
    sem_mae = _quantidade(rebanho, "nascidos_sem_mae")
    eventos_pendentes = _quantidade(rebanho, "eventos_pendentes_sincronizacao")
    nascimentos_estimados = _quantidade(rebanho, "com_nascimento_estimado")
    divergencias = _quantidade(rebanho, "dispositivos_com_divergencia")
    sem_manejo = _faltam(total, _quantidade(rebanho, "com_identificacao_manejo"))
    movimentacoes_vencidas = _quantidade(rebanho, "movimentacoes_abertas_vencidas")

    faltantes = (
        sem_oficial,
        sem_propriedade,
        sem_mae,
        eventos_pendentes,
        nascimentos_estimados,
        divergencias,
    )

    if antes_do_prazo:
        mensagem_oficial = (
            f"{sem_oficial} animais estão em preparo para a "
            "identificação oficial exigível no trânsito a partir de "
            "2033-01-01."
        )
    else:
        mensagem_oficial = _frase(
            sem_oficial,
            "animal sem identificação oficial",
            "animais sem identificação oficial",
        )

    mensagens = [
        mensagem_oficial,
        _frase(
            sem_propriedade,
            "animal sem propriedade definida",
            "animais sem propriedade definida",
        ),
        _frase(
            sem_mae,
            "animal nascido sem mãe vinculada",
            "animais nascidos sem mãe vinculada",
        ),
        _frase(
            eventos_pendentes,
            "evento pendente de sincronização",
            "eventos pendentes de sincronização",
        ),
        _frase(
            nascimentos_estimados,
            "animal com nascimento estimado",
            "animais com nascimento estimado",
        ),
        _frase(
            divergencias,
            "dispositivo com divergência",
            "dispositivos com divergência",
        ),
    ]

    return _IndicadoresRebanho(
        faltantes=faltantes,
        mensagens=mensagens,
        sem_manejo=sem_manejo,
        movimentacoes_vencidas=movimentacoes_vencidas,
    )


def _obter_pendencias_criticas(
    indicadores: _IndicadoresRebanho, antes_do_prazo: bool
) -> list[str]:
    pendencias_criticas: list[str] = []
    for indice, (faltam, mensagem) in enumerate(
        zip(indicadores.faltantes, indicadores.mensagens)
    ):
        if faltam and not (indice == 0 and antes_do_prazo):
            pendencias_criticas.append(mensagem)
    return pendencias_criticas


def _obter_pendencias_informativas(
    total: int, indicadores: _IndicadoresRebanho, antes_do_prazo: bool
) -> list[str]:
    pendencias_informativas: list[str] = []
    if total and indicadores.sem_manejo:
        pendencias_informativas.append(
            _frase(
                indicadores.sem_manejo,
                "animal sem identificação de manejo",
                "animais sem identificação de manejo",
            )
        )
    if total and indicadores.movimentacoes_vencidas:
        pendencias_informativas.append(
            _frase(
                indicadores.movimentacoes_vencidas,
                "movimentação aberta vencida",
                "movimentações abertas vencidas",
            )
        )
    if total and antes_do_prazo and indicadores.faltantes[0]:
        pendencias_informativas.append(indicadores.mensagens[0])
    return pendencias_informativas


def avaliar(rebanho: dict, referencia: str) -> dict:
    """Escore de conformidade e pendências, por dimensão.

    O resultado é um indicador de gestão baseado nos dados recebidos. Ele não
    constitui certificação nem afirmação de conformidade legal.
    """
    data_referencia = date.fromisoformat(referencia)
    total = _quantidade(rebanho, "animais_ativos")
    antes_do_prazo = data_referencia < _PRAZO_IDENTIFICACAO

    indicadores = _extrair_indicadores(rebanho, total, antes_do_prazo)

    dimensoes = [
        _dimensao(
            definicao,
            total,
            faltam,
            mensagem,
            nota=100.0 if indice == 0 and antes_do_prazo else None,
        )
        for indice, (definicao, faltam, mensagem) in enumerate(
            zip(_DIMENSOES, indicadores.faltantes, indicadores.mensagens)
        )
    ]
    escore = round(
        sum(item["peso"] * item["nota"] / 100.0 for item in dimensoes),
        2,
    )

    return {
        "escore": escore,
        "faixa": _faixa(escore),
        "dimensoes": dimensoes,
        "pendencias_criticas": _obter_pendencias_criticas(indicadores, antes_do_prazo),
        "pendencias_informativas": _obter_pendencias_informativas(
            total, indicadores, antes_do_prazo
        ),
        "prazo_relevante": (
            _PRAZO_IDENTIFICACAO.isoformat() if antes_do_prazo else None
        ),
    }
