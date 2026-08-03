#!/usr/bin/env python
"""Mapeia cores literais de app.py para os tokens definidos em ui.tema."""

import io
import math
import re
import sys
import tokenize
from collections import Counter
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[1]
PADRAO_HEX = re.compile(r"(?<![0-9a-fA-F])#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?![0-9a-fA-F])")


def _normalizar(cor: str) -> str:
    valor = cor.lower()
    if not re.fullmatch(r"#[0-9a-f]{3}|#[0-9a-f]{6}", valor):
        raise ValueError(f"Cor hexadecimal inválida: {cor}")
    if len(valor) == 4:
        valor = "#" + "".join(canal * 2 for canal in valor[1:])
    return valor


def _fragmento_de_url(texto: str, inicio: int) -> bool:
    prefixo = texto[:inicio]
    return bool(
        re.search(r"https?://[^\s\"']*$", prefixo, re.IGNORECASE)
        or re.search(r"(?:href|src)\s*=\s*[\"']?$", prefixo, re.IGNORECASE)
        or re.search(r"url\(\s*$", prefixo, re.IGNORECASE)
        or prefixo.endswith("](")
    )


def extrair_hex(codigo: str) -> list[dict]:
    """Todos os hex literais de um código Python.

    Retorna [{"hex": "#4ade80", "linha": int, "contexto": str}, ...].
    """
    linhas = codigo.splitlines()
    tipos_string = {tokenize.STRING}
    if hasattr(tokenize, "FSTRING_MIDDLE"):
        tipos_string.add(tokenize.FSTRING_MIDDLE)

    encontrados = []
    tokens = tokenize.generate_tokens(io.StringIO(codigo).readline)
    for token in tokens:
        if token.type not in tipos_string:
            continue
        for correspondencia in PADRAO_HEX.finditer(token.string):
            if _fragmento_de_url(token.string, correspondencia.start()):
                continue
            linha = token.start[0] + token.string[:correspondencia.start()].count("\n")
            contexto = linhas[linha - 1].strip() if linha <= len(linhas) else ""
            encontrados.append({
                "hex": _normalizar(correspondencia.group()),
                "linha": linha,
                "contexto": contexto,
            })
    return encontrados


def _lab(cor: str) -> tuple[float, float, float]:
    valor = _normalizar(cor)
    canais = [int(valor[i:i + 2], 16) / 255.0 for i in (1, 3, 5)]
    r, g, b = [
        canal / 12.92 if canal <= 0.04045 else ((canal + 0.055) / 1.055) ** 2.4
        for canal in canais
    ]
    x = (0.4124564 * r + 0.3575761 * g + 0.1804375 * b) / 0.95047
    y = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b
    z = (0.0193339 * r + 0.1191920 * g + 0.9503041 * b) / 1.08883

    delta = 6 / 29

    def f(valor_xyz: float) -> float:
        if valor_xyz > delta ** 3:
            return valor_xyz ** (1 / 3)
        return valor_xyz / (3 * delta ** 2) + 4 / 29

    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def distancia(hex_a: str, hex_b: str) -> float:
    """Distância perceptual CIE76 entre duas cores, 0 = idênticas."""
    lab_a = _lab(hex_a)
    lab_b = _lab(hex_b)
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(lab_a, lab_b)))


def _tokens_do_tema(tema: dict) -> list[tuple[str, str]]:
    tokens = []
    vistos = set()
    for paleta in tema.values():
        for nome, cor in paleta.items():
            par = (nome, _normalizar(cor))
            if par not in vistos:
                vistos.add(par)
                tokens.append(par)
    return tokens


def mapear(hexes: list[dict], tema: dict) -> dict:
    """Casa cada hex com o token de mesmo valor e sugere o mais próximo."""
    contagens = Counter(_normalizar(item["hex"]) for item in hexes)
    tokens = _tokens_do_tema(tema)
    exatos = []
    sem_token = []

    for cor, ocorrencias in sorted(contagens.items()):
        token_exato = next((nome for nome, valor in tokens if valor == cor), None)
        if token_exato is not None:
            exatos.append({
                "hex": cor,
                "token": token_exato,
                "ocorrencias": ocorrencias,
            })
            continue

        if tokens:
            nome, _ = min(tokens, key=lambda item: distancia(cor, item[1]))
            menor_distancia = min(
                distancia(cor, valor) for token, valor in tokens if token == nome
            )
        else:
            nome = ""
            menor_distancia = float("inf")
        sem_token.append({
            "hex": cor,
            "ocorrencias": ocorrencias,
            "mais_proximo": nome,
            "distancia": menor_distancia,
        })

    sem_token.sort(key=lambda item: (-item["ocorrencias"], item["hex"]))
    return {
        "exatos": exatos,
        "sem_token": sem_token,
        "resumo": {
            "total": sum(contagens.values()),
            "distintos": len(contagens),
            "com_token": len(exatos),
            "sem_token": len(sem_token),
        },
    }


def _cor_mais_proxima(cor: str, token: str, tema: dict) -> str:
    valores = [
        _normalizar(paleta[token])
        for paleta in tema.values()
        if token in paleta
    ]
    return min(valores, key=lambda valor: distancia(cor, valor))


def _imprimir_relatorio(resultado: dict, tema: dict) -> None:
    resumo = resultado["resumo"]
    ocorrencias_exatas = sum(item["ocorrencias"] for item in resultado["exatos"])
    ocorrencias_sem_token = sum(
        item["ocorrencias"] for item in resultado["sem_token"]
    )
    print(f'{resumo["total"]} hex em app.py · {resumo["distintos"]} distintos')
    print(
        f'  com token exato:  {resumo["com_token"]} '
        f'({ocorrencias_exatas} ocorrências)'
    )
    print(
        f'  sem token:         {resumo["sem_token"]} '
        f'({ocorrencias_sem_token} ocorrências)'
    )

    print("\nCOM TOKEN EXATO")
    for item in resultado["exatos"]:
        print(
            f'  {item["hex"]}  {item["ocorrencias"]:>3}x  '
            f'token: {item["token"]}'
        )

    print("\nSEM TOKEN (candidatos a token novo)")
    for item in resultado["sem_token"]:
        token = item["mais_proximo"]
        if token:
            cor_token = _cor_mais_proxima(item["hex"], token, tema)
            proximo = f"{token} ({cor_token})"
            distancia_texto = f'{item["distancia"]:.1f}'
        else:
            proximo = "nenhum"
            distancia_texto = "∞"
        print(
            f'  {item["hex"]}  {item["ocorrencias"]:>3}x  '
            f'mais próximo: {proximo}, distância {distancia_texto}'
        )


def main() -> int:
    if str(RAIZ) not in sys.path:
        sys.path.insert(0, str(RAIZ))
    from ui.tema import TEMAS

    codigo = (RAIZ / "app.py").read_text(encoding="utf-8")
    resultado = mapear(extrair_hex(codigo), TEMAS)
    _imprimir_relatorio(resultado, TEMAS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
