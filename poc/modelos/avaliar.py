"""Mede a curva de aprendizado de um regressor linear para o próximo GMD."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


JANELAS_MESES = (3, 6, 12, 18, 24)
LOTES = ("P1", "P2", "P3", "P4")


def _ler_pesagens(caminho: Path) -> dict[str, list[dict]]:
    por_animal: dict[str, list[dict]] = defaultdict(list)
    with caminho.open(encoding="utf-8", newline="") as arquivo:
        for linha in csv.DictReader(arquivo):
            por_animal[linha["animal_id"]].append({
                "data": date.fromisoformat(linha["data"]),
                "peso": float(linha["peso_kg"]),
                "lote_id": linha["lote_id"],
                "metodo": linha["metodo"],
                "idade_dias": int(linha["idade_dias"]),
            })
    for pesagens in por_animal.values():
        pesagens.sort(key=lambda item: item["data"])
    return por_animal


def _montar_amostras(por_animal: dict[str, list[dict]]) -> list[dict]:
    amostras: list[dict] = []
    for pesagens in por_animal.values():
        for indice in range(1, len(pesagens) - 1):
            anterior, atual, seguinte = pesagens[indice - 1:indice + 2]
            dias_atual = (atual["data"] - anterior["data"]).days
            dias_alvo = (seguinte["data"] - atual["data"]).days
            if dias_atual <= 0 or dias_alvo <= 0:
                continue
            gmd_atual = (atual["peso"] - anterior["peso"]) / dias_atual
            gmd_alvo = (seguinte["peso"] - atual["peso"]) / dias_alvo
            if not (-1.0 <= gmd_atual <= 3.0 and -1.0 <= gmd_alvo <= 3.0):
                continue
            amostras.append({
                "data_alvo": seguinte["data"],
                "gmd_atual": gmd_atual,
                "gmd_alvo": gmd_alvo,
                "peso": atual["peso"],
                "idade_dias": atual["idade_dias"],
                "lote_id": atual["lote_id"],
                "estimado": atual["metodo"] == "estimado",
                "dia_ano": atual["data"].timetuple().tm_yday,
            })
    return amostras


def _matriz(amostras: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    linhas = []
    alvos = []
    for item in amostras:
        angulo = 2.0 * np.pi * item["dia_ano"] / 365.25
        linhas.append([
            item["gmd_atual"],
            item["peso"],
            item["idade_dias"],
            np.sin(angulo),
            np.cos(angulo),
            float(item["estimado"]),
            *(1.0 if item["lote_id"] == lote else 0.0 for lote in LOTES[:-1]),
        ])
        alvos.append(item["gmd_alvo"])
    return np.asarray(linhas, dtype=float), np.asarray(alvos, dtype=float)


def _ajustar_e_prever(treino: list[dict], teste: list[dict]) -> np.ndarray:
    x_treino, y_treino = _matriz(treino)
    x_teste, _ = _matriz(teste)
    media = x_treino.mean(axis=0)
    desvio = x_treino.std(axis=0)
    desvio[desvio == 0.0] = 1.0
    x_treino = (x_treino - media) / desvio
    x_teste = (x_teste - media) / desvio
    x_treino = np.column_stack((np.ones(len(x_treino)), x_treino))
    x_teste = np.column_stack((np.ones(len(x_teste)), x_teste))
    coeficientes, *_ = np.linalg.lstsq(x_treino, y_treino, rcond=None)
    return x_teste @ coeficientes


def avaliar(caminho: Path) -> list[dict]:
    amostras = _montar_amostras(_ler_pesagens(caminho))
    ultima_data = max(item["data_alvo"] for item in amostras)
    inicio_teste = ultima_data - timedelta(days=180)
    teste = [item for item in amostras if item["data_alvo"] >= inicio_teste]
    y_teste = np.asarray([item["gmd_alvo"] for item in teste])
    ingenua = np.asarray([item["gmd_atual"] for item in teste])
    erro_ingenuo = float(np.mean(np.abs(y_teste - ingenua)))

    resultados = []
    for meses in JANELAS_MESES:
        inicio_treino = inicio_teste - timedelta(days=round(meses * 30.4375))
        treino = [
            item for item in amostras
            if inicio_treino <= item["data_alvo"] < inicio_teste
        ]
        previsao = _ajustar_e_prever(treino, teste)
        erro_modelo = float(np.mean(np.abs(y_teste - previsao)))
        resultados.append({
            "meses": meses,
            "amostras_treino": len(treino),
            "amostras_teste": len(teste),
            "mae_modelo_kg_dia": erro_modelo,
            "mae_ingenua_kg_dia": erro_ingenuo,
            "ganho_kg_dia": erro_ingenuo - erro_modelo,
        })
    return resultados


def _salvar_csv(resultados: list[dict], caminho: Path) -> None:
    with caminho.open("w", encoding="utf-8", newline="") as arquivo:
        writer = csv.DictWriter(arquivo, fieldnames=list(resultados[0]))
        writer.writeheader()
        for resultado in resultados:
            writer.writerow({
                chave: round(valor, 4) if isinstance(valor, float) else valor
                for chave, valor in resultado.items()
            })


def _salvar_grafico(resultados: list[dict], caminho: Path) -> None:
    meses = [item["meses"] for item in resultados]
    modelo = [item["mae_modelo_kg_dia"] for item in resultados]
    ingenua = [item["mae_ingenua_kg_dia"] for item in resultados]
    fig, eixo = plt.subplots(figsize=(8, 4.8))
    eixo.plot(meses, modelo, marker="o", linewidth=2, label="Regressão linear")
    eixo.plot(meses, ingenua, linestyle="--", linewidth=2, label="Linha de base ingênua")
    eixo.set(
        title="Erro de previsão do próximo GMD por histórico disponível",
        xlabel="Meses de histórico usados no treino",
        ylabel="MAE (kg/dia; menor é melhor)",
        xticks=meses,
    )
    eixo.grid(alpha=0.25)
    eixo.legend()
    fig.tight_layout()
    fig.savefig(caminho, dpi=160)
    plt.close(fig)


def main() -> None:
    pasta = Path(__file__).parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--dados", type=Path, default=pasta / "dados_sinteticos.csv")
    parser.add_argument("--csv", type=Path, default=pasta / "curva_aprendizado.csv")
    parser.add_argument("--grafico", type=Path, default=pasta / "curva_aprendizado.png")
    args = parser.parse_args()

    resultados = avaliar(args.dados)
    _salvar_csv(resultados, args.csv)
    _salvar_grafico(resultados, args.grafico)
    for item in resultados:
        print(
            f"{item['meses']:>2} meses | treino={item['amostras_treino']:>4} | "
            f"modelo={item['mae_modelo_kg_dia']:.3f} kg/dia | "
            f"ingênua={item['mae_ingenua_kg_dia']:.3f} kg/dia | "
            f"ganho={item['ganho_kg_dia']:.3f} kg/dia"
        )


if __name__ == "__main__":
    main()
