"""Leitura de camadas Shapefile exportadas pelo cadastro ambiental rural."""

from __future__ import annotations

import io
import json
import math
import re
import unicodedata
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Iterable

import shapefile
from pyproj import CRS, Transformer
from shapely.geometry import Polygon
from shapely.ops import transform

from services.geometria import area_hectares, validar


@dataclass(frozen=True)
class CamadaCar:
    """Uma camada CAR com seus anéis em longitude/latitude."""

    tipo: str
    poligonos: list[list[tuple[float, float]]]
    area_ha_atributo: float | None = None


_ROTULOS = {
    "area_imovel": "Área do Imóvel",
    "perimetro_imovel": "Área do Imóvel",
    "app": "APP",
    "reserva_legal": "Reserva Legal",
    "vegetacao_nativa": "Vegetação Nativa",
    "hidrografia": "Hidrografia",
    "area_consolidada": "Área Consolidada",
    "uso_restrito": "Uso Restrito",
    "servidao_administrativa": "Servidão Administrativa",
    "area_pousio": "Área de Pousio",
    "nascente": "Nascente",
}


def _normalizar(valor: object) -> str:
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "_", texto.lower()).strip("_")


def _rotulo_camada(nome: str, registros: list[dict]) -> str | None:
    valores = [_normalizar(nome)]
    for registro in registros[:20]:
        for chave in ("cod_tema", "nom_tema", "tema", "tipo", "classe", "layer"):
            if chave in registro:
                valores.append(_normalizar(registro[chave]))
    texto = "_".join(valores)
    for chave, rotulo in _ROTULOS.items():
        if chave in texto:
            return rotulo
    return None


def _crs_do_prj(prj: bytes | None, coordenadas: list[tuple[float, float]]) -> CRS | None:
    if not prj:
        if all(-180 <= x <= 180 and -90 <= y <= 90 for x, y in coordenadas):
            return None
        raise ValueError("O Shapefile não informa o sistema de coordenadas (.prj).")
    try:
        return CRS.from_wkt(prj.decode("utf-8", errors="replace"))
    except Exception as exc:
        raise ValueError("O sistema de coordenadas do Shapefile é inválido.") from exc


def _anéis_shape(shape, transformador) -> list[list[tuple[float, float]]]:
    pontos = list(shape.points)
    partes = list(shape.parts) + [len(pontos)]
    anéis = []
    for inicio, fim in zip(partes, partes[1:]):
        anel = [transformador(*ponto) for ponto in pontos[inicio:fim]]
        if len(anel) > 1 and anel[0] == anel[-1]:
            anel.pop()
        if len(anel) >= 3 and not validar(anel):
            anéis.append([(float(x), float(y)) for x, y in anel])
    return anéis


def _valor_area(registros: list[dict]) -> float | None:
    if not registros:
        return None
    chaves = list(registros[0])
    candidata = next((k for k in chaves if _normalizar(k) in {
        "num_area", "area_ha", "area_hectares", "area_imovel", "area"
    }), None)
    if candidata is None:
        return None
    valores = []
    for registro in registros:
        try:
            valor = float(registro[candidata])
        except (TypeError, ValueError):
            continue
        if math.isfinite(valor) and valor >= 0:
            valores.append(valor)
    return valores[0] if valores else None


def _ler_arquivos_zip(conteudo_zip: bytes) -> list[tuple[str, dict[str, bytes]]]:
    try:
        arquivo = zipfile.ZipFile(io.BytesIO(conteudo_zip))
    except (zipfile.BadZipFile, TypeError) as exc:
        raise ValueError("O arquivo não é um .zip válido.") from exc
    arquivos = {PurePosixPath(nome).as_posix(): arquivo.read(nome)
                for nome in arquivo.namelist() if not nome.endswith("/")}
    encontrados = []
    for nome, dados in arquivos.items():
        if nome.lower().endswith(".zip"):
            encontrados.extend(_ler_arquivos_zip(dados))
    grupos: dict[str, dict[str, bytes]] = {}
    for nome, dados in arquivos.items():
        sufixo = PurePosixPath(nome).suffix.lower()
        if sufixo in {".shp", ".shx", ".dbf", ".prj"}:
            grupos.setdefault(str(PurePosixPath(nome).with_suffix("")), {})[sufixo[1:]] = dados
    encontrados.extend((base, grupo) for base, grupo in grupos.items())
    return encontrados


def _ler_grupo(nome: str, arquivos: dict[str, bytes]) -> tuple[str, CamadaCar] | None:
    if not {"shp", "shx", "dbf"}.issubset(arquivos):
        return None
    try:
        leitor = shapefile.Reader(
            shp=io.BytesIO(arquivos["shp"]),
            shx=io.BytesIO(arquivos["shx"]),
            dbf=io.BytesIO(arquivos["dbf"]),
            encoding="latin1",
        )
        campos = [campo[0] for campo in leitor.fields[1:]]
        registros = [dict(zip(campos, registro)) for registro in leitor.records()]
        rotulo = _rotulo_camada(PurePosixPath(nome).name, registros)
        if rotulo is None:
            return None
        formas = list(leitor.shapes())
        pontos = [tuple(p) for forma in formas for p in forma.points]
        crs = _crs_do_prj(arquivos.get("prj"), pontos)
        transformador = (lambda x, y: (x, y))
        if crs is not None and crs.to_epsg() != 4326:
            para_wgs84 = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
            transformador = para_wgs84.transform
        poligonos = [anel for forma in formas
                     if forma.shapeType in (5, 15, 25)
                     for anel in _anéis_shape(forma, transformador)]
        if not poligonos:
            return None
        return rotulo, CamadaCar(rotulo, poligonos, _valor_area(registros))
    except (shapefile.ShapefileException, OSError, ValueError) as exc:
        raise ValueError("O .zip contém um Shapefile inválido.") from exc


def ler_shapefile_car(conteudo_zip: bytes) -> dict[str, list[CamadaCar]]:
    """Lê um .zip de Shapefile e agrupa as camadas CAR reconhecidas."""
    grupos = _ler_arquivos_zip(conteudo_zip)
    resultado: dict[str, list[CamadaCar]] = {}
    for nome, arquivos in grupos:
        camada = _ler_grupo(nome, arquivos)
        if camada is None:
            continue
        tipo, item = camada
        resultado.setdefault(tipo, []).append(item)
    if not resultado:
        raise ValueError("O .zip não contém um Shapefile CAR reconhecível.")
    if "Área do Imóvel" not in resultado:
        raise ValueError("Nenhuma camada reconhecível como perímetro do imóvel foi encontrada.")
    return resultado


def area_camada_ha(camada: CamadaCar) -> float:
    if camada.area_ha_atributo is not None:
        return float(camada.area_ha_atributo)
    return sum(area_hectares(anel) for anel in camada.poligonos)


def percentual_sobreposicao(
    propriedade: list[tuple[float, float]],
    car_poligonos: Iterable[list[tuple[float, float]]],
) -> float:
    """Percentual da área cadastrada coberta pelos polígonos do CAR."""
    if validar(propriedade):
        return 0.0
    car_poligonos = list(car_poligonos)
    if not car_poligonos:
        return 0.0
    base = Polygon(propriedade)
    if base.is_empty or base.area == 0:
        return 0.0
    centro = base.centroid
    zona = min(60, max(1, math.floor((centro.x + 180.0) / 6.0) + 1))
    crs = CRS.from_dict({"proj": "utm", "zone": zona, "south": centro.y < 0,
                         "datum": "WGS84", "units": "m"})
    para_utm = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    base_utm = transform(para_utm.transform, base)
    car_utm = [transform(para_utm.transform, Polygon(anel))
               for anel in car_poligonos if not validar(anel)]
    if not car_utm:
        return 0.0
    intersecao = base_utm.intersection(car_utm[0])
    for poligono in car_utm[1:]:
        intersecao = intersecao.union(base_utm.intersection(poligono))
    return round(max(0.0, min(100.0, float(intersecao.area / base_utm.area * 100.0))), 2)


def camada_para_geojson(camada: CamadaCar) -> str:
    if len(camada.poligonos) == 1:
        coordenadas = [[[float(x), float(y)] for x, y in camada.poligonos[0]]]
        geometria = {"type": "Polygon", "coordinates": coordenadas}
    else:
        coordenadas = [[[[float(x), float(y)] for x, y in anel]]
                       for anel in camada.poligonos]
        geometria = {"type": "MultiPolygon", "coordinates": coordenadas}
    return json.dumps(geometria, ensure_ascii=False)
