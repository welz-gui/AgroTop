"""Importação pura de pesagens exportadas por indicadores de balança."""

import csv
from datetime import date, datetime


def _detectar_separador(linhas: list[str]) -> str:
    return ";" if any(";" in linha for linha in linhas) else ","


def _eh_cabecalho(colunas: list[str]) -> bool:
    if len(colunas) != 3:
        return False
    nomes = [coluna.strip().casefold() for coluna in colunas]
    return (
        nomes[0] in {"animal", "animal_id", "brinco", "id", "id animal"}
        and nomes[1] in {"peso", "peso (kg)", "peso_kg", "weight"}
        and nomes[2] in {"data", "date"}
    )


def _parse_data(valor: str) -> date | None:
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(valor, formato).date()
        except ValueError:
            pass
    return None


def parse_pesagens(
    texto: str,
    *,
    ids_conhecidos: set[str] | None = None,
) -> dict:
    """Interpreta um CSV de pesagens.

    `ids_conhecidos`: brincos existentes no rebanho. Se None, não valida existência.
    (É injetado justamente para a função não precisar do banco.)

    Retorna:
        {
          "aceitas":   [{"animal_id": str, "peso": float, "data": "YYYY-MM-DD"}, ...],
          "rejeitadas":[{"linha": int, "conteudo": str, "motivo": str}, ...],
          "total_linhas": int,
        }
    """
    resultado = {"aceitas": [], "rejeitadas": [], "total_linhas": 0}
    linhas = texto.splitlines()
    nao_vazias = [linha for linha in linhas if linha.strip()]
    if not nao_vazias:
        return resultado

    separador = _detectar_separador(nao_vazias)
    primeira_linha = True

    for numero, conteudo in enumerate(linhas, start=1):
        if not conteudo.strip():
            continue

        try:
            colunas = next(csv.reader([conteudo], delimiter=separador))
        except csv.Error:
            colunas = []

        if primeira_linha:
            primeira_linha = False
            if _eh_cabecalho(colunas):
                continue

        resultado["total_linhas"] += 1
        motivo = None

        if len(colunas) != 3:
            motivo = f"esperado 3 colunas, encontrado {len(colunas)}"
        else:
            animal_id, peso_texto, data_texto = (
                coluna.strip() for coluna in colunas
            )

            if not animal_id:
                motivo = "brinco vazio"
            else:
                try:
                    peso = float(peso_texto.replace(",", "."))
                except ValueError:
                    motivo = f"peso inválido: '{peso_texto}'"
                else:
                    if peso <= 0 or peso > 1500:
                        motivo = (
                            f"peso fora da faixa plausível: {peso:g} kg"
                        )
                    else:
                        data_pesagem = _parse_data(data_texto)
                        if data_pesagem is None:
                            motivo = f"data inválida: '{data_texto}'"
                        elif data_pesagem > date.today():
                            motivo = (
                                f"data no futuro: {data_pesagem.isoformat()}"
                            )
                        elif (
                            ids_conhecidos is not None
                            and animal_id not in ids_conhecidos
                        ):
                            motivo = f"animal não encontrado: {animal_id}"
                        else:
                            resultado["aceitas"].append(
                                {
                                    "animal_id": animal_id,
                                    "peso": peso,
                                    "data": data_pesagem.isoformat(),
                                }
                            )

        if motivo is not None:
            resultado["rejeitadas"].append(
                {"linha": numero, "conteudo": conteudo, "motivo": motivo}
            )

    return resultado
