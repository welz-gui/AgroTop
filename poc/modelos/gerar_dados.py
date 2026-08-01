"""Gera pesagens sintéticas para estudar a curva de aprendizado de GMD.

Os dados não representam o rebanho real do AgroTop. As premissas foram escolhidas
para reproduzir ordem de grandeza, sazonalidade e ruído esperados em gado de corte.
"""

from __future__ import annotations

import argparse
import csv
from datetime import date, timedelta
from pathlib import Path

import numpy as np


LOTES = ("P1", "P2", "P3", "P4")
EFEITO_LOTE = {"P1": -0.08, "P2": -0.02, "P3": 0.05, "P4": 0.10}


def _lote_no_periodo(lote_inicial: int, dias_desde_inicio: int) -> str:
    """Simula rotação semestral entre quatro piquetes."""
    rotacoes = dias_desde_inicio // 180
    return LOTES[(lote_inicial + rotacoes) % len(LOTES)]


def gerar(
    caminho: Path,
    *,
    animais: int = 200,
    meses: int = 30,
    semente: int = 20260731,
) -> None:
    rng = np.random.default_rng(semente)
    inicio = date(2023, 1, 1)
    fim = inicio + timedelta(days=round(meses * 30.4375))
    linhas: list[dict] = []

    for indice in range(animais):
        animal_id = f"A{indice + 1:04d}"
        lote_inicial = indice % len(LOTES)
        efeito_individual = rng.normal(0.0, 0.09)
        idade_dias = int(rng.integers(430, 680))
        peso_real = float(np.clip(rng.normal(275.0, 32.0), 190.0, 360.0))
        data_pesagem = inicio + timedelta(days=int(rng.integers(0, 15)))
        desvio_temporal = 0.0

        while data_pesagem <= fim:
            dias_desde_inicio = (data_pesagem - inicio).days
            lote = _lote_no_periodo(lote_inicial, dias_desde_inicio)
            metodo = "estimado" if rng.random() < 0.10 else "pesado"
            ruido_peso = 9.0 if metodo == "estimado" else 3.5
            peso_observado = max(1.0, peso_real + rng.normal(0.0, ruido_peso))

            linhas.append({
                "animal_id": animal_id,
                "data": data_pesagem.isoformat(),
                "peso_kg": round(peso_observado, 2),
                "peso_real_kg": round(peso_real, 2),
                "lote_id": lote,
                "metodo": metodo,
                "idade_dias": idade_dias,
            })

            intervalo = int(rng.integers(35, 56))
            proxima_data = data_pesagem + timedelta(days=intervalo)
            if proxima_data > fim:
                break

            meio_periodo = data_pesagem + timedelta(days=intervalo // 2)
            # Em MT, a estação chuvosa favorece o ganho; a seca reduz o GMD.
            sazonalidade = 0.18 * np.cos(2.0 * np.pi * (meio_periodo.timetuple().tm_yday - 30) / 365.25)
            # O ganho desacelera conforme o animal se aproxima do peso de saída.
            maturidade = -0.0009 * max(0.0, peso_real - 300.0)
            desvio_temporal = 0.55 * desvio_temporal + rng.normal(0.0, 0.07)
            gmd_real = float(np.clip(
                0.72 + efeito_individual + EFEITO_LOTE[lote] + sazonalidade
                + maturidade + desvio_temporal,
                0.05,
                1.45,
            ))

            peso_real += gmd_real * intervalo
            idade_dias += intervalo
            data_pesagem = proxima_data

    linhas.sort(key=lambda item: (item["data"], item["animal_id"]))
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8", newline="") as arquivo:
        writer = csv.DictWriter(arquivo, fieldnames=list(linhas[0]))
        writer.writeheader()
        writer.writerows(linhas)

    print(
        f"Geradas {len(linhas)} pesagens sintéticas de {animais} animais "
        f"entre {inicio.isoformat()} e {fim.isoformat()} em {caminho}."
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--saida", type=Path, default=Path(__file__).with_name("dados_sinteticos.csv"))
    parser.add_argument("--animais", type=int, default=200)
    parser.add_argument("--meses", type=int, default=30)
    parser.add_argument("--semente", type=int, default=20260731)
    args = parser.parse_args()
    gerar(args.saida, animais=args.animais, meses=args.meses, semente=args.semente)


if __name__ == "__main__":
    main()
