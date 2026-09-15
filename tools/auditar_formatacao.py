#!/usr/bin/env python
"""Audita a formatação de números decimais e datas em app.py."""

import argparse
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

PADRAO_DECIMAL = re.compile(r":\.[0-9]f}")
PADRAO_DATA = re.compile(r"\.isoformat\(\)")

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def classificar_decimal(linha: str) -> str:
    """Classifica ocorrência de formatação decimal em 'interno' ou 'visivel'."""
    # Plotly templates (avaliados client-side pelo motor JS do Plotly)
    if (
        "hovertemplate=" in linha
        or "texttemplate=" in linha
        or "%{" in linha
    ):
        return "interno"
    # Notas salvas no banco de dados
    if "medida_nota =" in linha:
        return "interno"
    # Estilo inline CSS (layout HTML, exige ponto/inteiro pela sintaxe CSS)
    if "width:{" in linha or "height:{" in linha:
        return "interno"
    return "visivel"


def classificar_data(linha: str) -> str:
    """Classifica ocorrência de .isoformat() em 'interno' ou 'visivel'."""
    # Datas exibidas ao usuário em tabelas, cards ou mensagens de aviso
    if (
        "Carência até" in linha
        or "carência" in linha
        or "st.warning" in linha
    ):
        return "visivel"
    return "interno"


def extrair_ocorrencias(codigo: str) -> dict:
    """Extrai todas as ocorrências de formatação decimal e datas com classificação.

    Retorna dict com listas 'decimais' e 'datas', cada item contendo:
    {'tipo': str, 'linha': int, 'trecho': str, 'classificacao': str}
    """
    linhas = codigo.splitlines()
    decimais = []
    datas = []

    for i, linha in enumerate(linhas, 1):
        if PADRAO_DECIMAL.search(linha):
            decimais.append({
                "tipo": "decimal",
                "linha": i,
                "trecho": linha.strip(),
                "classificacao": classificar_decimal(linha),
            })
        if PADRAO_DATA.search(linha):
            datas.append({
                "tipo": "data",
                "linha": i,
                "trecho": linha.strip(),
                "classificacao": classificar_data(linha),
            })

    return {
        "decimais": decimais,
        "datas": datas,
        "resumo": {
            "total_decimal": len(decimais),
            "decimal_visivel": sum(1 for d in decimais if d["classificacao"] == "visivel"),
            "decimal_interno": sum(1 for d in decimais if d["classificacao"] == "interno"),
            "total_data": len(datas),
            "data_visivel": sum(1 for d in datas if d["classificacao"] == "visivel"),
            "data_interno": sum(1 for d in datas if d["classificacao"] == "interno"),
            "total_geral": len(decimais) + len(datas),
        },
    }


def imprimir_relatorio(resultado: dict, mostrar_detalhes: bool = True) -> None:
    """Imprime o relatório de auditoria de formatação."""
    res = resultado["resumo"]
    print("=" * 70)
    print("RELATÓRIO DE AUDITORIA DE FORMATAÇÃO (app.py)")
    print("=" * 70)
    print(f"Total decimal (:.Nf}}): {res['total_decimal']} ocorrências")
    print(f"  - Visível ao usuário:   {res['decimal_visivel']:>3}")
    print(f"  - Interno / exportação: {res['decimal_interno']:>3}")
    print()
    print(f"Total datas (.isoformat()): {res['total_data']} ocorrências")
    print(f"  - Visível ao usuário:   {res['data_visivel']:>3}")
    print(f"  - Interno / exportação: {res['data_interno']:>3}")
    print()
    print(f"Total geral: {res['total_geral']} ocorrências")
    print("=" * 70)

    if mostrar_detalhes:
        print("\nOCORRÊNCIAS DECIMAIS (:.Nf}):")
        print("-" * 70)
        for item in resultado["decimais"]:
            tag = "[VISÍVEL]" if item["classificacao"] == "visivel" else "[INTERNO]"
            print(f"Linha {item['linha']:>4} {tag:<10} | {item['trecho']}")

        print("\nOCORRÊNCIAS DE DATA (.isoformat()):")
        print("-" * 70)
        for item in resultado["datas"]:
            tag = "[VISÍVEL]" if item["classificacao"] == "visivel" else "[INTERNO]"
            print(f"Linha {item['linha']:>4} {tag:<10} | {item['trecho']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--arquivo",
        type=Path,
        default=RAIZ / "app.py",
        help="Arquivo a ser auditado (padrão: app.py)",
    )
    parser.add_argument(
        "--apenas-resumo",
        action="store_true",
        help="Não exibe a lista completa de linhas, apenas o resumo numérico",
    )
    args = parser.parse_args(argv)

    caminho = args.arquivo
    if not caminho.is_file():
        print(f"Erro: arquivo não encontrado: {caminho}", file=sys.stderr)
        return 1

    codigo = caminho.read_text(encoding="utf-8")
    resultado = extrair_ocorrencias(codigo)
    imprimir_relatorio(resultado, mostrar_detalhes=not args.apenas_resumo)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
