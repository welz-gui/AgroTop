"""Reproduz a coleta de cenas Sentinel-2 e calcula NDVI médio para um polígono em MT."""

import datetime
import os
import time
from typing import Any, Dict, List

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from rasterio.enums import Resampling
from rasterio.mask import mask
from rasterio.vrt import WarpedVRT
from rasterio.warp import transform_geom
import requests
from shapely.geometry import Polygon, mapping

# Fonte pública STAC do Sentinel-2 L2A COGs via Earth Search v1.
STAC_SEARCH_URL = "https://earth-search.aws.element84.com/v1/search"
STAC_COLLECTION = "sentinel-2-l2a"

# Polígono de pastagem plausível em Mato Grosso, ~30 ha.
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

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_IMAGE = os.path.join(OUTPUT_DIR, "ndvi_timeseries.png")
OUTPUT_NDVI_CSV = os.path.join(OUTPUT_DIR, "ndvi_timeseries.csv")
OUTPUT_CLOUD_CSV = os.path.join(OUTPUT_DIR, "cloud_cover_monthly.csv")
OUTPUT_SCENES_CSV = os.path.join(OUTPUT_DIR, "scene_cloud_cover.csv")

# Classes SCL que representam superfície observável. Nuvem, cirrus, sombra e neve ficam fora.
SCL_VALID_CLASSES = (4, 5, 6, 7)


def stac_search(start_date: datetime.date, end_date: datetime.date) -> pd.DataFrame:
    """Busca metadados de cenas Sentinel-2 dentro do período e do polígono."""
    payload = {
        "collections": [STAC_COLLECTION],
        "datetime": (
            f"{start_date.isoformat()}T00:00:00Z/"
            f"{end_date.isoformat()}T23:59:59Z"
        ),
        "intersects": {
            "type": "Polygon",
            "coordinates": [list(PASTURE_POLYGON.exterior.coords)],
        },
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
        rows.append({
            "scene_id": scene_id,
            "date": scene_date,
            "cloud_cover": float(cloud),
            "properties": props,
            "assets": feature.get("assets", {}),
        })

    return pd.DataFrame(rows)


def summarize_cloud_cover(df: pd.DataFrame) -> pd.DataFrame:
    """Agrupa por mês e calcula nuvem média e cenas utilizáveis por limiar."""
    monthly_source = df.copy()
    monthly_source["month"] = monthly_source["date"].apply(lambda d: d.replace(day=1))
    for threshold in (10, 20, 40):
        monthly_source[f"usable_{threshold}"] = (
            monthly_source["cloud_cover"] <= threshold
        ).astype(int)
    return (
        monthly_source.groupby("month")
        .agg(
            total_scenes=("scene_id", "count"),
            mean_cloud=("cloud_cover", "mean"),
            usable_10=("usable_10", "sum"),
            usable_20=("usable_20", "sum"),
            usable_40=("usable_40", "sum"),
        )
        .reset_index()
    )


def threshold_usage(df: pd.DataFrame, max_cloud: float) -> pd.DataFrame:
    return df[df["cloud_cover"] <= max_cloud].copy()


def largest_gap(
    dates: pd.Series,
    start_date: datetime.date = START_DATE,
    end_date: datetime.date = END_DATE,
) -> int:
    """Retorna o maior intervalo sem cena, incluindo as bordas do período."""
    boundaries = pd.to_datetime([start_date, end_date])
    normalized = pd.to_datetime(dates.dropna()).dt.normalize()
    normalized = normalized[(normalized >= boundaries[0]) & (normalized <= boundaries[1])]
    all_dates = pd.Series([boundaries[0], *normalized.drop_duplicates(), boundaries[1]])
    deltas = all_dates.sort_values().drop_duplicates().diff().dt.days.dropna()
    return int(deltas.max()) if not deltas.empty else 0


def get_assets(scene: pd.Series) -> Dict[str, Any]:
    return scene["assets"] if "assets" in scene else {}


def _asset(assets: Dict[str, Any], name: str) -> Dict[str, Any]:
    asset = assets.get(name, {})
    if not asset.get("href"):
        raise ValueError(f"Cena sem ativo {name!r} necessário para NDVI.")
    return asset


def _scale_and_offset(asset: Dict[str, Any]) -> tuple[float, float]:
    bands = asset.get("raster:bands") or [{}]
    return float(bands[0].get("scale", 1.0)), float(bands[0].get("offset", 0.0))


def compute_ndvi_mean(assets: Dict[str, Any]) -> float:
    """Calcula NDVI médio do polígono com B04/B08 e máscara SCL da cena."""
    red_asset = _asset(assets, "red")
    nir_asset = _asset(assets, "nir")
    scl_asset = _asset(assets, "scl")

    raster_env = {
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
        "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
    }
    with rasterio.Env(**raster_env):
        with (
            rasterio.open(red_asset["href"]) as src_red,
            rasterio.open(nir_asset["href"]) as src_nir,
            rasterio.open(scl_asset["href"]) as src_scl,
        ):
            geom = mapping(PASTURE_POLYGON)
            geom_proj = transform_geom("EPSG:4326", src_red.crs, geom, precision=6)

            red_data, _ = mask(src_red, [geom_proj], crop=True, filled=False)
            nir_data, _ = mask(src_nir, [geom_proj], crop=True, filled=False)
            with WarpedVRT(
                src_scl,
                crs=src_red.crs,
                transform=src_red.transform,
                width=src_red.width,
                height=src_red.height,
                resampling=Resampling.nearest,
            ) as aligned_scl:
                scl_data, _ = mask(aligned_scl, [geom_proj], crop=True, filled=False)

    red_scale, red_offset = _scale_and_offset(red_asset)
    nir_scale, nir_offset = _scale_and_offset(nir_asset)
    red = np.ma.asarray(red_data[0], dtype="float32") * red_scale + red_offset
    nir = np.ma.asarray(nir_data[0], dtype="float32") * nir_scale + nir_offset
    scl = np.ma.asarray(scl_data[0])

    red_values = np.ma.getdata(red)
    nir_values = np.ma.getdata(nir)
    denominator = nir_values + red_values
    valid = ~(
        np.ma.getmaskarray(red)
        | np.ma.getmaskarray(nir)
        | np.ma.getmaskarray(scl)
    )
    valid &= np.isin(np.ma.getdata(scl), SCL_VALID_CLASSES)
    valid &= np.isfinite(red_values) & np.isfinite(nir_values)
    valid &= (red_values > 0.0) & (nir_values > 0.0) & (denominator != 0.0)

    if not np.any(valid):
        raise ValueError("Nenhum pixel de superfície válido no polígono após a máscara SCL.")

    ndvi = (nir_values[valid] - red_values[valid]) / denominator[valid]
    return float(np.mean(ndvi))


def plot_ndvi_series(series: pd.Series) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(series.index, series.values, marker="o", linestyle="-", color="#2b7b2b")
    ax.set_title("NDVI médio do polígono em imagens utilizáveis")
    ax.set_xlabel("Data da cena")
    ax.set_ylabel("NDVI médio")
    ax.grid(True, alpha=0.3)
    fig.autofmt_xdate(rotation=45)
    fig.tight_layout()
    fig.savefig(OUTPUT_IMAGE)
    plt.close(fig)


def main() -> None:
    print("Polígono de teste: aproximadamente 30 ha em Mato Grosso")
    print(f"Período: {START_DATE} até {END_DATE}")

    scenes = stac_search(START_DATE, END_DATE)
    if scenes.empty:
        print("Nenhuma cena encontrada. Verifique a fonte STAC ou o polígono.")
        return

    scenes = scenes.sort_values("date")
    print(f"Cenas encontradas: {len(scenes)}")
    scenes[["scene_id", "date", "cloud_cover"]].to_csv(
        OUTPUT_SCENES_CSV, index=False, float_format="%.4f"
    )
    print(f"Cobertura por cena salva em {OUTPUT_SCENES_CSV}")

    thresholds = [10.0, 20.0, 40.0]
    for threshold in thresholds:
        usable = threshold_usage(scenes, threshold)
        gap = largest_gap(pd.to_datetime(usable["date"]))
        print(
            f"Cenas <= {threshold:.0f}% nuvem: {len(usable)}; "
            f"maior vão: {gap} dias"
        )

    monthly = summarize_cloud_cover(scenes)
    monthly.to_csv(OUTPUT_CLOUD_CSV, index=False, float_format="%.1f")
    print("Resumo mensal de cobertura de nuvem:")
    print(monthly.to_string(index=False, float_format="{:.1f}".format))
    print(f"Tabela mensal salva em {OUTPUT_CLOUD_CSV}")

    ndvi_threshold = 20.0
    usable_ndvi = threshold_usage(scenes, ndvi_threshold)
    if usable_ndvi.empty:
        print(f"Nenhuma cena com nuvem <= {ndvi_threshold}% para cálculo de NDVI.")
        return

    ndvi_rows = []
    for _, row in usable_ndvi.iterrows():
        last_error = None
        for attempt in range(1, 4):
            try:
                ndvi_value = compute_ndvi_mean(get_assets(row))
                ndvi_rows.append({
                    "scene_id": row["scene_id"],
                    "date": row["date"],
                    "cloud_cover": row["cloud_cover"],
                    "ndvi": ndvi_value,
                })
                print(f"NDVI médio {row['date']}: {ndvi_value:.4f}")
                break
            except Exception as exc:
                last_error = exc
                if attempt < 3:
                    time.sleep(2)
        else:
            print(f"Falha ao calcular NDVI para {row['scene_id']}: {last_error}")

    if ndvi_rows:
        ndvi_df = pd.DataFrame(ndvi_rows).sort_values("date")
        ndvi_df.to_csv(OUTPUT_NDVI_CSV, index=False, float_format="%.4f")
        ndvi_series = pd.Series(data=ndvi_df["ndvi"].values, index=ndvi_df["date"])
        plot_ndvi_series(ndvi_series)
        amplitude = ndvi_df["ndvi"].max() - ndvi_df["ndvi"].min()
        print(
            f"NDVI calculado em {len(ndvi_df)}/{len(usable_ndvi)} cenas; "
            f"amplitude observada: {amplitude:.4f}"
        )
        print(f"Série salva em {OUTPUT_NDVI_CSV}")
        print(f"Gráfico salvo em {OUTPUT_IMAGE}")
    else:
        print("Nenhum valor NDVI calculado; nenhum gráfico foi gerado.")


if __name__ == "__main__":
    main()
