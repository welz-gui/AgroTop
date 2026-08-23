"""Leitura pura de arquivos de lotes de dispositivos de identificação."""

import csv
import re
import unicodedata

from services.estados_dispositivo import conferir_codigos


_COLUNAS = (
    "codigo_visual",
    "codigo_eletronico",
    "tipo",
    "fabricante",
    "modelo",
    "lote",
    "data_fabricacao",
)


def _normalizar_coluna(valor: str) -> str:
    sem_acentos = "".join(
        caractere
        for caractere in unicodedata.normalize("NFKD", valor)
        if not unicodedata.combining(caractere)
    )
    return re.sub(r"[^a-z0-9]+", "_", sem_acentos.casefold()).strip("_")


def _separador(linhas: list[str]) -> str:
    for linha in linhas:
        if ";" in linha:
            return ";"
        if "," in linha:
            return ","
    return ";"


def _ler_colunas(conteudo: str, separador: str) -> list[str] | None:
    try:
        return next(csv.reader([conteudo], delimiter=separador, strict=True))
    except csv.Error:
        return None


def _eh_rodape(conteudo: str) -> bool:
    return bool(re.match(r"^\s*total\s*:", conteudo, flags=re.IGNORECASE))


def _criar_resultado_vazio() -> dict:
    return {
        "aceitos": [],
        "rejeitados": [],
        "duplicados_no_arquivo": [],
        "total_linhas": 0,
        "colunas_detectadas": [],
    }


def _rejeitar(resultado: dict, numero: int, conteudo: str, motivo: str) -> None:
    resultado["rejeitados"].append(
        {"linha": numero, "conteudo": conteudo, "motivo": motivo}
    )


def _rejeitar_todas(linhas: list[str], resultado: dict) -> None:
    for numero, conteudo in enumerate(linhas, start=1):
        resultado["total_linhas"] += 1
        motivo = (
            "linha vazia"
            if not conteudo.strip()
            else "rodapé de totais não é um dispositivo"
            if _eh_rodape(conteudo)
            else "CSV inválido"
        )
        _rejeitar(resultado, numero, conteudo, motivo)


def _configurar_colunas(primeira: list[str] | None) -> tuple[bool, dict, int, list[str]]:
    nomes_cabecalho = (
        [_normalizar_coluna(valor) for valor in primeira]
        if primeira is not None
        else []
    )
    tem_cabecalho = any(nome in _COLUNAS for nome in nomes_cabecalho)

    if tem_cabecalho:
        indices = {
            nome: indice
            for indice, nome in enumerate(nomes_cabecalho)
            if nome in _COLUNAS and nome not in nomes_cabecalho[:indice]
        }
        colunas_detectadas = [nome for nome in nomes_cabecalho if nome in indices]
        quantidade_esperada = len(primeira) if primeira else 0
    else:
        quantidade_esperada = len(primeira or [])
        colunas_detectadas = list(_COLUNAS[:quantidade_esperada])
        indices = {nome: indice for indice, nome in enumerate(colunas_detectadas)}

    return tem_cabecalho, indices, quantidade_esperada, colunas_detectadas


def _processar_linha(
    conteudo: str,
    numero: int,
    separador: str,
    quantidade_esperada: int,
    tem_cabecalho: bool,
    indices: dict,
    vistos: set[str],
    duplicados: set[str],
    resultado: dict,
) -> None:
    if not conteudo.strip():
        _rejeitar(resultado, numero, conteudo, "linha vazia")
        return
    if _eh_rodape(conteudo):
        _rejeitar(resultado, numero, conteudo, "rodapé de totais não é um dispositivo")
        return

    valores = _ler_colunas(conteudo, separador)
    if valores is None:
        _rejeitar(resultado, numero, conteudo, "CSV inválido")
        return
    if len(valores) != quantidade_esperada:
        motivo = f"esperado {quantidade_esperada} colunas, encontrado {len(valores)}"
        _rejeitar(resultado, numero, conteudo, motivo)
        return
    if not tem_cabecalho and quantidade_esperada > len(_COLUNAS):
        _rejeitar(resultado, numero, conteudo, f"máximo de {len(_COLUNAS)} colunas reconhecidas")
        return

    item = {nome: "" for nome in _COLUNAS}
    for nome, indice in indices.items():
        item[nome] = valores[indice].strip()

    codigo_visual = item["codigo_visual"]
    if not codigo_visual:
        _rejeitar(resultado, numero, conteudo, "código visual vazio")
        return

    chave = codigo_visual.casefold()
    if chave in vistos:
        if chave not in duplicados:
            resultado["duplicados_no_arquivo"].append(codigo_visual)
            duplicados.add(chave)
        _rejeitar(
            resultado,
            numero,
            conteudo,
            f"código visual duplicado no arquivo: {codigo_visual}"
        )
        return

    vistos.add(chave)
    resultado["aceitos"].append(item)


def ler(texto: str) -> dict:
    """Interpreta um arquivo de lote de dispositivos.

    Aceita CSV com `;` ou `,`, com ou sem cabeçalho. Colunas reconhecidas
    (em qualquer ordem, nomes tolerantes a acento e caixa):
      codigo_visual (obrigatória) · codigo_eletronico · tipo · fabricante ·
      modelo · lote · data_fabricacao

    Retorna {
      "aceitos":   [{"codigo_visual","codigo_eletronico","tipo",...}, ...],
      "rejeitados":[{"linha": int, "conteudo": str, "motivo": str}, ...],
      "duplicados_no_arquivo": [str, ...],
      "total_linhas": int,
      "colunas_detectadas": [str, ...],
    }
    """
    resultado = _criar_resultado_vazio()
    linhas = texto.splitlines()
    if not linhas:
        return resultado

    separador = _separador(linhas)
    indice_modelo = next(
        (
            indice
            for indice, linha in enumerate(linhas)
            if linha.strip()
            and not _eh_rodape(linha)
            and _ler_colunas(linha, separador) is not None
        ),
        None,
    )

    if indice_modelo is None:
        _rejeitar_todas(linhas, resultado)
        return resultado

    primeira = _ler_colunas(linhas[indice_modelo], separador)
    tem_cabecalho, indices, quantidade_esperada, col_detectadas = _configurar_colunas(primeira)
    resultado["colunas_detectadas"] = col_detectadas

    vistos: set[str] = set()
    duplicados: set[str] = set()

    for indice_linha, conteudo in enumerate(linhas):
        if tem_cabecalho and indice_linha == indice_modelo:
            continue

        numero = indice_linha + 1
        resultado["total_linhas"] += 1

        _processar_linha(
            conteudo,
            numero,
            separador,
            quantidade_esperada,
            tem_cabecalho,
            indices,
            vistos,
            duplicados,
            resultado,
        )

    return resultado


def conferir_pareamento(itens: list[dict], *,
                        digitos_comparados: int = 0) -> list[dict]:
    """Divergências entre visual e eletrônico no próprio arquivo (§5.3).

    Usa `services.estados_dispositivo.conferir_codigos` — não reimplementa.
    Retorna [{"codigo_visual", "codigo_eletronico", "divergencia"}, ...]
    """
    divergencias = []
    for item in itens:
        codigo_visual = item.get("codigo_visual", "")
        codigo_eletronico = item.get("codigo_eletronico", "")
        conferencia = conferir_codigos(
            codigo_visual,
            codigo_eletronico,
            digitos_comparados=digitos_comparados,
        )
        if not conferencia["confere"]:
            divergencias.append(
                {
                    "codigo_visual": codigo_visual,
                    "codigo_eletronico": codigo_eletronico,
                    "divergencia": conferencia["divergencia"],
                }
            )
    return divergencias
