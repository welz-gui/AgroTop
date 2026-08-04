"""Escore gerencial de conformidade e pendências do rebanho."""

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
    return f"{quantidade} {unidade}"


def _dimensao(
    nome: str,
    peso: float,
    total: int,
    faltam: int,
    mensagem: str,
    *,
    nota: float | None = None,
) -> dict:
    return {
        "nome": nome,
        "peso": peso,
        "nota": _nota(total, faltam) if nota is None else nota,
        "faltam": faltam,
        "mensagem": f"{mensagem} {_AVISO}",
    }


def _faixa(escore: float) -> str:
    if escore >= 100.0:
        return "conforme"
    if escore >= 85.0:
        return "bom"
    if escore >= 70.0:
        return "atencao"
    return "critico"


def avaliar(rebanho: dict, referencia: str) -> dict:
    """Escore de conformidade e pendências, por dimensão.

    O resultado é um indicador de gestão baseado nos dados recebidos. Ele não
    constitui certificação nem afirmação de conformidade legal.
    """
    data_referencia = date.fromisoformat(referencia)
    total = _quantidade(rebanho, "animais_ativos")

    sem_oficial = _faltam(
        total, _quantidade(rebanho, "com_identificacao_oficial")
    )
    sem_propriedade = _faltam(
        total, _quantidade(rebanho, "com_propriedade")
    )
    sem_mae = _quantidade(rebanho, "nascidos_sem_mae")
    eventos_pendentes = _quantidade(
        rebanho, "eventos_pendentes_sincronizacao"
    )
    nascimentos_estimados = _quantidade(
        rebanho, "com_nascimento_estimado"
    )
    divergencias = _quantidade(
        rebanho, "dispositivos_com_divergencia"
    )
    antes_do_prazo = data_referencia < _PRAZO_IDENTIFICACAO

    if total == 0:
        mensagem_vazia = "Sem animais ativos para avaliar."
        mensagens = [mensagem_vazia] * 6
    else:
        if antes_do_prazo:
            mensagem_oficial = (
                f"{sem_oficial} animais ainda estão em preparo para a "
                "identificação oficial exigível no trânsito a partir de 2033-01-01."
            )
        else:
            mensagem_oficial = _frase(
                sem_oficial,
                "animal sem identificação oficial",
                "animais sem identificação oficial",
            ) + "."
        mensagens = [
            mensagem_oficial,
            _frase(
                sem_propriedade,
                "animal sem propriedade definida",
                "animais sem propriedade definida",
            ) + ".",
            _frase(
                sem_mae,
                "animal nascido sem mãe vinculada",
                "animais nascidos sem mãe vinculada",
            ) + ".",
            _frase(
                eventos_pendentes,
                "evento pendente de sincronização",
                "eventos pendentes de sincronização",
            ) + ".",
            _frase(
                nascimentos_estimados,
                "animal com nascimento estimado",
                "animais com nascimento estimado",
            ) + ".",
            _frase(
                divergencias,
                "dispositivo com divergência",
                "dispositivos com divergência",
            ) + ".",
        ]

    faltantes = (
        sem_oficial,
        sem_propriedade,
        sem_mae,
        eventos_pendentes,
        nascimentos_estimados,
        divergencias,
    )
    dimensoes = [
        _dimensao(
            definicao["nome"],
            definicao["peso"],
            total,
            faltam,
            mensagem,
            nota=100.0 if indice == 0 and antes_do_prazo else None,
        )
        for indice, (definicao, faltam, mensagem) in enumerate(
            zip(_DIMENSOES, faltantes, mensagens)
        )
    ]
    escore = round(
        sum(item["peso"] * item["nota"] / 100.0 for item in dimensoes),
        2,
    )

    pendencias_criticas: list[str] = []
    if sem_oficial and not antes_do_prazo:
        pendencias_criticas.append(mensagens[0])
    if sem_propriedade:
        pendencias_criticas.append(mensagens[1])
    if sem_mae:
        pendencias_criticas.append(mensagens[2])
    if eventos_pendentes:
        pendencias_criticas.append(mensagens[3])

    sem_manejo = _faltam(
        total, _quantidade(rebanho, "com_identificacao_manejo")
    )
    if sem_manejo:
        pendencias_criticas.append(
            _frase(
                sem_manejo,
                "animal sem identificação de manejo",
                "animais sem identificação de manejo",
            ) + "."
        )

    movimentacoes_vencidas = _quantidade(
        rebanho, "movimentacoes_abertas_vencidas"
    )
    if movimentacoes_vencidas:
        pendencias_criticas.append(
            _frase(
                movimentacoes_vencidas,
                "movimentação aberta vencida",
                "movimentações abertas vencidas",
            ) + "."
        )
    if divergencias:
        pendencias_criticas.append(mensagens[5])

    return {
        "escore": escore,
        "faixa": _faixa(escore),
        "dimensoes": dimensoes,
        "pendencias_criticas": pendencias_criticas,
        "prazo_relevante": (
            _PRAZO_IDENTIFICACAO.isoformat() if antes_do_prazo else None
        ),
    }
