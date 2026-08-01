"""Reproduz a coleta de cenas Sentinel-2 e calcula NDVI médio para um polígono em MT."""

import datetime
import os
from typing import Any, Dict, List

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from rasterio.mask import mask
from rasterio.warp import transform_geom
import requests
from shapely.geometry import Polygon, mapping

# Fonte pública STAC do Sentinel-2 L2A COGs via Earth Search.
STAC_SEARCH_URL = "https://earth-search.aws.element84.com/v0/search"

# Polígono de pastagem plausível em Mato Grosso, ~20 ha.
# Coordenadas no formato [lon, lat].
PASTURE_POLYGON = Polygon([
    (-55.9000, -13.3000),
    (-55.9000, -13.2950),
    (-55.8950, -13.2950),
    (-55.8950, -13.3000),
    (-55.9000, -13.3000),
])

START_DATE = datetime.date(2025, 5, 1)
END_DATE = datetime.date(2026, 4, 30)

OUTPUT_IMAGE = "poc/ndvi/ndvi_timeseries.png"


def stac_search(start_date: datetime.date, end_date: datetime.date) -> pd.DataFrame:
    """Busca metadados de cenas Sentinel-2 dentro do período e do polígono."""
    payload = {
        "collections": ["sentinel-s2-l2a-cogs"],
        "datetime": f"{start_date.isoformat()}/{end_date.isoformat()}",
        "intersects": {
            "type": "Polygon",
            "coordinates": [list(PASTURE_POLYGON.exterior.coords)],
        },
        "query": {"eo:cloud_cover": {"lt": 100}},
        "limit": 250,
    }

    response = requests.post(STAC_SEARCH_URL, json=payload, timeout=60)
    response.raise_for_status()
    data = response.json()

    features = data.get("features", [])
    rows: List[Dict[str, Any]] = []
    for feature in features:
        props = feature.get("properties", {})
        scene_id = feature.get("id")
        date_str = props.get("datetime")
        cloud = props.get("eo:cloud_cover")
        if date_str is None or cloud is None:
            continue
        try:
            scene_date = pd.to_datetime(date_str).date()
        except ValueError:
            continue
        rows.append({"scene_id": scene_id, "date": scene_date, "cloud_cover": float(cloud), "properties": props, "assets": feature.get("assets", {})})

    return pd.DataFrame(rows)


def summarize_cloud_cover(df: pd.DataFrame) -> pd.DataFrame:
    """Agrupa por mês e calcula a nuvem média e cenas utilizáveis."""
    df = df.copy()
    df["month"] = df["date"].apply(lambda d: d.replace(day=1))
    monthly = (
        df.groupby("month")
        .agg(total_scenes=("scene_id", "count"), mean_cloud=("cloud_cover", "mean"))
        .reset_index()
    )
    return monthly


def threshold_usage(df: pd.DataFrame, max_cloud: float) -> pd.DataFrame:
    return df[df["cloud_cover"] <= max_cloud].copy()


def largest_gap(dates: pd.Series) -> int:
    """Retorna a maior interrupção entre cenas utilizáveis, em dias."""
    if dates.empty:
        return (END_DATE - START_DATE).days
    sorted_dates = dates.drop_duplicates().sort_values()
    deltas = sorted_dates.diff().dt.days.dropna()
    if deltas.empty:
        return 0
    return int(deltas.max())


def get_assets(scene: pd.Series) -> Dict[str, Any]:
    return scene["assets"] if "assets" in scene else {}


def compute_ndvi_mean(asset_urls: Dict[str, Any]) -> float:
    """Calcula o NDVI médio da cena usando as bandas B04 e B08 em COGs remotos."""
    b04_url = asset_urls.get("B04", {}).get("href")
    b08_url = asset_urls.get("B08", {}).get("href")
    if not b04_url or not b08_url:
        raise ValueError("Cenas sem ativos B04 ou B08 suficientes para NDVI.")

    with rasterio.open(b04_url) as src_b04, rasterio.open(b08_url) as src_b08:
        geom = mapping(PASTURE_POLYGON)
        geom_proj = transform_geom("EPSG:4326", src_b04.crs, geom, precision=6)

        b04_data, _ = mask(src_b04, [geom_proj], crop=True, filled=False)
        b08_data, _ = mask(src_b08, [geom_proj], crop=True, filled=False)

        b04 = np.asarray(b04_data[0], dtype="float32")
        b08 = np.asarray(b08_data[0], dtype="float32")

        b04 = np.ma.masked_invalid(b04)
        b08 = np.ma.masked_invalid(b08)
        valid = ~(np.ma.getmaskarray(b04) | np.ma.getmaskarray(b08))

        if not np.any(valid):
            raise ValueError("Nenhum pixel válido encontrado no polígono para esta cena.")

        b04 = np.ma.filled(b04, fill_value=0.0)
        b08 = np.ma.filled(b08, fill_value=0.0)
        numerator = b08 - b04
        denominator = b08 + b04
        valid = valid & (denominator != 0.0)
        ndvi = np.full_like(numerator, np.nan, dtype="float32")
        ndvi[valid] = numerator[valid] / denominator[valid]
        ndvi = np.ma.masked_invalid(ndvi)

        return float(np.ma.mean(ndvi))


def plot_ndvi_series(series: pd.Series) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(series.index, series.values, marker="o", linestyle="-", color="#2b7b2b")
    ax.set_title("NDVI médio do polígono em imagens utilizáveis")
    ax.set_xlabel("Data da cena")
    ax.set_ylabel("NDVI médio")
    ax.grid(True, alpha=0.3)
    fig.autofmt_xdate(rotation=45)
    os.makedirs(os.path.dirname(OUTPUT_IMAGE), exist_ok=True)
    fig.tight_layout()
    fig.savefig(OUTPUT_IMAGE)
    plt.close(fig)


def main() -> None:
    print("Polígono de teste: 20 ha plausível em Mato Grosso")
    print(f"Período: {START_DATE} até {END_DATE}")

    scenes = stac_search(START_DATE, END_DATE)
    if scenes.empty:
        print("Nenhuma cena encontrada. Verifique a fonte STAC ou o polígono.")
        return

    print(f"Cenas encontradas: {len(scenes)}")
    scenes = scenes.sort_values("date")

    thresholds = [10.0, 20.0, 40.0]
    for threshold in thresholds:
        usable = threshold_usage(scenes, threshold)
        print(f"Cenas <= {threshold}% nuvem: {len(usable)}")

    for threshold in thresholds:
        usable = threshold_usage(scenes, threshold)
        gap = largest_gap(pd.to_datetime(usable["date"]))
        print(f"Maior vão com nuvem <= {threshold}%: {gap} dias")

    monthly = summarize_cloud_cover(scenes)
    print("Resumo mensal de cobertura de nuvem:")
    print(monthly.to_string(index=False, float_format="{:.1f}".format))

    ndvi_threshold = 20.0
    usable_ndvi = threshold_usage(scenes, ndvi_threshold)
    if usable_ndvi.empty:
        print(f"Nenhuma cena com nuvem <= {ndvi_threshold}% para cálculo de NDVI.")
        return

    ndvi_rows = []
    for _, row in usable_ndvi.iterrows():
        try:
            ndvi_value = compute_ndvi_mean(get_assets(row))
            ndvi_rows.append({"date": row["date"], "ndvi": ndvi_value})
            print(f"NDVI médio {row['date']}: {ndvi_value:.4f}")
        except Exception as exc:
            print(f"Falha ao calcular NDVI para {row['scene_id']}: {exc}")

    if ndvi_rows:
        ndvi_df = pd.DataFrame(ndvi_rows).sort_values("date")
        ndvi_series = pd.Series(data=ndvi_df["ndvi"].values, index=ndvi_df["date"])
        plot_ndvi_series(ndvi_series)
        print(f"Gráfico de série temporal salvo em {OUTPUT_IMAGE}")
    else:
        print("Nenhum valor NDVI calculado; verifique os ativos das cenas.")

    if "SENTINEL_API_KEY" in os.environ:
        print("Variável de ambiente SENTINEL_API_KEY definida, mas este script usa fonte pública STAC gratuita.")


if __name__ == "__main__":
    main()
