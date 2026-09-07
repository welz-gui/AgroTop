"""Cálculo de NDVI por piquete a partir de imagens do Sentinel-2.

Este módulo consulta o catálogo público STAC do Sentinel-2 L2A (Earth Search
v1, coleção `sentinel-2-l2a`) e lê os Cloud-Optimized GeoTIFFs (COGs)
hospedados no programa de Dados Abertos da AWS para calcular o NDVI médio de
um piquete.

Regra de ouro (ROADMAP Trilha 4 / Spec 0079):
- NDVI não equivale a kg de matéria seca — nenhum alerta deve afirmar
  disponibilidade de forragem sem calibração de campo.
- Esta leitura é para acompanhamento de tendência e conferência periódica;
  a cobertura de nuvem na chuva (maior vão de até ~105 dias) inviabiliza
  monitoramento contínuo ou alerta em tempo quase real.
- Nenhuma chave de API é necessária ou utilizada para o Earth Search v1.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import os
from typing import Any, Dict, List, Tuple

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.mask import mask
from rasterio.vrt import WarpedVRT
from rasterio.warp import transform_geom
import requests
from shapely.geometry import Polygon, mapping

# Endpoint público do Earth Search v1 (Element 84 / AWS Open Data).
# Acesso aberto, sem necessidade de credenciais ou cadastro.
STAC_SEARCH_URL = os.environ.get(
    "AGROTOP_STAC_URL",
    "https://earth-search.aws.element84.com/v1/search",
)
STAC_COLLECTION = "sentinel-2-l2a"

# Classes da banda SCL que representam superfície observável.
# 4: vegetação, 5: solo não vegetado, 6: água, 7: neve/gelo não derretido.
# Nuvens (8, 9), cirrus (10), sombra (3), saturação (1) e nodata (0) saem.
SCL_VALID_CLASSES = (4, 5, 6, 7)


class NdviError(Exception):
    """Exceção base do módulo NDVI."""
    pass


class NdviIndisponivelError(NdviError):
    """Lançada quando o serviço STAC ou COG está indisponível."""
    pass


@dataclass
class NdviPonto:
    """Ponto individual da série temporal de NDVI."""
    data: date
    ndvi_medio: float
    nuvem_pct_cena: float
    id_da_cena: str


@dataclass
class NdviResultado:
    """Resultado da consulta de NDVI para um piquete em um período."""
    serie: List[NdviPonto]
    maior_vao_dias: int
    total_cenas_buscadas: int
    total_cenas_utilizaveis: int


def calcular_maior_vao(datas: List[date], inicio: date, fim: date) -> int:
    """Calcula o maior intervalo em dias sem imagem utilizável no período.

    Inclui expressamente as bordas do período:
    - do `inicio` até a data da primeira cena;
    - entre cenas consecutivas;
    - da última cena até a data de `fim`.
    """
    if inicio > fim:
        return 0

    datas_validas = sorted({d for d in datas if inicio <= d <= fim})
    todas = sorted({inicio, *datas_validas, fim})
    if len(todas) <= 1:
        return 0

    vaos = [(todas[i] - todas[i - 1]).days for i in range(1, len(todas))]
    return max(vaos) if vaos else 0


def buscar_cenas_stac(
    poligono_coords: List[Tuple[float, float]],
    inicio: date,
    fim: date,
    timeout: int = 60,
) -> List[Dict[str, Any]]:
    """Busca metadados de cenas Sentinel-2 no Earth Search v1."""
    coords = list(poligono_coords)
    if coords[0] != coords[-1]:
        coords.append(coords[0])

    payload = {
        "collections": [STAC_COLLECTION],
        "datetime": (
            f"{inicio.isoformat()}T00:00:00Z/"
            f"{fim.isoformat()}T23:59:59Z"
        ),
        "intersects": {
            "type": "Polygon",
            "coordinates": [coords],
        },
        "limit": 250,
    }

    try:
        response = requests.post(
            STAC_SEARCH_URL, json=payload, timeout=timeout
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise NdviIndisponivelError(
            f"Falha na comunicação com o serviço STAC do Sentinel-2: {exc}"
        ) from exc

    features = data.get("features", [])
    cenas: List[Dict[str, Any]] = []
    for feat in features:
        props = feat.get("properties", {})
        scene_id = feat.get("id")
        date_str = props.get("datetime")
        cloud = props.get("eo:cloud_cover")
        if not scene_id or date_str is None or cloud is None:
            continue
        try:
            scene_date = date.fromisoformat(date_str[:10])
        except (ValueError, TypeError):
            continue

        cenas.append({
            "scene_id": scene_id,
            "date": scene_date,
            "cloud_cover": float(cloud),
            "assets": feat.get("assets", {}),
            "properties": props,
        })
    return cenas


def _obter_ativo(assets: Dict[str, Any], *nomes: str) -> Dict[str, Any]:
    for nome in nomes:
        asset = assets.get(nome, {})
        if asset.get("href"):
            return asset
    raise ValueError(f"Cena sem ativo {nomes!r} necessário para NDVI.")


def _escala_e_offset(asset: Dict[str, Any]) -> Tuple[float, float]:
    bands = asset.get("raster:bands") or [{}]
    scale = float(bands[0].get("scale", 1.0))
    offset = float(bands[0].get("offset", 0.0))
    return scale, offset


def calcular_ndvi_cena(assets: Dict[str, Any], poligono: Polygon) -> float:
    """Calcula NDVI médio do polígono a partir dos COGs Sentinel-2.

    Aplica máscara SCL (classes 4, 5, 6, 7) e escala/offset do metadado STAC.
    """
    red_asset = _obter_ativo(assets, "red", "B04", "b04")
    nir_asset = _obter_ativo(assets, "nir", "B08", "b08")
    scl_asset = _obter_ativo(assets, "scl", "SCL")

    raster_env = {
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
        "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
    }
    try:
        with rasterio.Env(**raster_env):
            with (
                rasterio.open(red_asset["href"]) as src_red,
                rasterio.open(nir_asset["href"]) as src_nir,
                rasterio.open(scl_asset["href"]) as src_scl,
            ):
                geom = mapping(poligono)
                crs_alvo = src_red.crs or "EPSG:4326"
                is_wgs84 = str(crs_alvo).upper() in (
                    "EPSG:4326", "WGS 84", "OGC:CRS84"
                )
                if is_wgs84:
                    geom_proj = geom
                else:
                    geom_proj = transform_geom(
                        "EPSG:4326", src_red.crs, geom, precision=6
                    )

                red_data, _ = mask(
                    src_red, [geom_proj], crop=True, filled=False
                )
                nir_data, _ = mask(
                    src_nir, [geom_proj], crop=True, filled=False
                )
                with WarpedVRT(
                    src_scl,
                    crs=src_red.crs,
                    transform=src_red.transform,
                    width=src_red.width,
                    height=src_red.height,
                    resampling=Resampling.nearest,
                ) as aligned_scl:
                    scl_data, _ = mask(
                        aligned_scl, [geom_proj], crop=True, filled=False
                    )
    except (rasterio.errors.RasterioError, OSError) as exc:
        raise NdviIndisponivelError(
            f"Erro ao acessar imagens raster (COG): {exc}"
        ) from exc

    red_scale, red_offset = _escala_e_offset(red_asset)
    nir_scale, nir_offset = _escala_e_offset(nir_asset)

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
        raise ValueError(
            "Nenhum pixel de superfície válido no polígono após a máscara SCL."
        )

    ndvi = (nir_values[valid] - red_values[valid]) / denominator[valid]
    return float(np.mean(ndvi))


def ndvi_do_piquete(
    poligono: List[Tuple[float, float]],
    inicio: date,
    fim: date,
    nuvem_max_pct: int = 20,
) -> NdviResultado:
    """Busca cenas Sentinel-2 (Earth Search v1) que cobrem o polígono.

    Filtra por `nuvem_max_pct`, calcula NDVI médio mascarado por SCL em cada
    cena utilizável. Devolve a série (pode ser vazia) mais o maior vão em
    dias — mesma definição de `largest_gap()` da PoC, incluindo bordas.
    """
    if not poligono or len(poligono) < 3:
        raise ValueError(
            "Polígono inválido: necessita de pelo menos 3 coordenadas."
        )
    if inicio > fim:
        raise ValueError(
            f"Data de início ({inicio}) posterior ao fim ({fim})."
        )

    coords = list(poligono)
    if coords[0] != coords[-1]:
        coords.append(coords[0])
    poligono_shapely = Polygon(coords)

    cenas = buscar_cenas_stac(coords, inicio, fim)
    total_cenas_buscadas = len(cenas)

    cenas_utilizaveis = [c for c in cenas if c["cloud_cover"] <= nuvem_max_pct]
    total_cenas_utilizaveis = len(cenas_utilizaveis)

    cenas_utilizaveis.sort(key=lambda c: (c["date"], c["scene_id"]))

    serie: List[NdviPonto] = []
    for cena in cenas_utilizaveis:
        try:
            ndvi_val = calcular_ndvi_cena(cena["assets"], poligono_shapely)
            serie.append(NdviPonto(
                data=cena["date"],
                ndvi_medio=round(ndvi_val, 4),
                nuvem_pct_cena=round(cena["cloud_cover"], 2),
                id_da_cena=cena["scene_id"],
            ))
        except ValueError:
            # Piquete coberto por nuvem local ou sem pixels válidos
            continue
        except NdviIndisponivelError:
            # Falha de rede no download/leitura parcial dos COGs
            raise

    datas_serie = [p.data for p in serie]
    maior_vao = calcular_maior_vao(datas_serie, inicio, fim)

    return NdviResultado(
        serie=serie,
        maior_vao_dias=maior_vao,
        total_cenas_buscadas=total_cenas_buscadas,
        total_cenas_utilizaveis=total_cenas_utilizaveis,
    )
