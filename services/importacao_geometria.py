"""Serviço de importação e leitura de perímetros de piquetes em arquivos GeoJSON e KML (funções puras).

Converte representações em GeoJSON e KML para listas de vértices [(lon, lat), ...]
em EPSG:4326 consumidas por `services.geometria`.
"""

import json
import xml.etree.ElementTree as ET


def ler_geojson(conteudo: str) -> list[tuple[float, float]]:
    """Extrai o anel de vértices de um GeoJSON com um único polígono.

    Aceita tanto uma geometria `Polygon` "nua" quanto um `Feature` (ou o
    primeiro Feature de um `FeatureCollection`) cuja geometria é `Polygon`.
    Usa o anel EXTERNO (primeiro anel de `coordinates`) — ignora buracos
    internos, se houver.

    Levanta `ValueError`, com mensagem em português, se: o texto não é JSON
    válido, o tipo de geometria não é `Polygon` (inclui recusar
    `MultiPolygon` explicitamente — um piquete é UM polígono; a ambiguidade
    de "qual dos vários" não deve ser resolvida silenciosamente), ou não há
    coordenadas suficientes.
    """
    if not isinstance(conteudo, str) or not conteudo.strip():
        raise ValueError("Conteúdo GeoJSON vazio ou inválido.")

    try:
        dados = json.loads(conteudo)
    except json.JSONDecodeError as e:
        raise ValueError(f"Texto não é um JSON válido: {e}") from e

    if not isinstance(dados, dict):
        raise ValueError("Conteúdo GeoJSON deve ser um objeto JSON.")

    tipo = dados.get("type")

    if tipo == "FeatureCollection":
        features = dados.get("features")
        if not isinstance(features, list) or len(features) == 0:
            raise ValueError("FeatureCollection não contém nenhum elemento 'features'.")
        primeiro = features[0]
        if not isinstance(primeiro, dict):
            raise ValueError("Primeiro elemento do FeatureCollection é inválido.")
        geom = primeiro.get("geometry")
        if not isinstance(geom, dict):
            raise ValueError("Primeiro Feature não possui uma geometria válida.")
    elif tipo == "Feature":
        geom = dados.get("geometry")
        if not isinstance(geom, dict):
            raise ValueError("Feature não possui uma geometria válida.")
    elif tipo in (
        "Polygon",
        "MultiPolygon",
        "Point",
        "LineString",
        "MultiPoint",
        "MultiLineString",
        "GeometryCollection",
    ) or "coordinates" in dados:
        geom = dados
    else:
        raise ValueError(f"Tipo de objeto GeoJSON desconhecido ou não suportado: '{tipo}'.")

    geom_type = geom.get("type")
    if geom_type == "MultiPolygon":
        raise ValueError("MultiPolygon não é suportado: um piquete deve ter apenas um polígono.")
    if geom_type != "Polygon":
        raise ValueError(f"Tipo de geometria '{geom_type}' não suportado. Esperado 'Polygon'.")

    coords = geom.get("coordinates")
    if not isinstance(coords, list) or len(coords) == 0:
        raise ValueError("Geometria Polygon sem coordenadas.")

    anel_externo = coords[0]
    if not isinstance(anel_externo, list) or len(anel_externo) == 0:
        raise ValueError("Anel externo de coordenadas do polígono está vazio.")

    vertices: list[tuple[float, float]] = []
    for pt in anel_externo:
        if not isinstance(pt, (list, tuple)) or len(pt) < 2:
            raise ValueError(f"Ponto de coordenada inválido no GeoJSON: {pt}.")
        try:
            lon = float(pt[0])
            lat = float(pt[1])
        except (ValueError, TypeError) as e:
            raise ValueError(f"Coordenada numérica inválida no GeoJSON: {pt}.") from e
        vertices.append((lon, lat))

    if not vertices:
        raise ValueError("Nenhum vértice pôde ser extraído do GeoJSON.")

    return vertices


def _tag_local(elem: ET.Element) -> str:
    return elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag


def _buscar_primeiro_por_tag(root: ET.Element, nome_tag: str) -> ET.Element | None:
    for elem in root.iter():
        if _tag_local(elem) == nome_tag:
            return elem
    return None


def ler_kml(conteudo: str) -> list[tuple[float, float]]:
    """Extrai o anel de vértices do primeiro `<Polygon>` de um KML.

    Lê `<outerBoundaryIs><LinearRing><coordinates>`. O KML aceita
    coordenadas com altitude (`lon,lat,alt`) separadas por espaço ou quebra
    de linha — descarte a altitude, ela não é usada em nenhum cálculo do
    módulo `geometria`.

    Levanta `ValueError`, com mensagem em português, se: o XML é inválido,
    não há nenhum `<Polygon>`, ou as coordenadas estão malformadas.
    """
    if not isinstance(conteudo, str) or not conteudo.strip():
        raise ValueError("Conteúdo KML vazio ou inválido.")

    try:
        root = ET.fromstring(conteudo.strip())
    except ET.ParseError as e:
        raise ValueError(f"XML KML inválido ou corrompido: {e}") from e

    poligono = _buscar_primeiro_por_tag(root, "Polygon")
    if poligono is None:
        raise ValueError("Nenhum elemento <Polygon> encontrado no KML.")

    outer = _buscar_primeiro_por_tag(poligono, "outerBoundaryIs")
    if outer is not None:
        ring = _buscar_primeiro_por_tag(outer, "LinearRing")
        if ring is None:
            raise ValueError("Elemento <LinearRing> não encontrado em <outerBoundaryIs> do KML.")
        coords_elem = _buscar_primeiro_por_tag(ring, "coordinates")
    else:
        ring = _buscar_primeiro_por_tag(poligono, "LinearRing")
        if ring is not None:
            coords_elem = _buscar_primeiro_por_tag(ring, "coordinates")
        else:
            coords_elem = _buscar_primeiro_por_tag(poligono, "coordinates")

    if coords_elem is None or coords_elem.text is None:
        raise ValueError("Elemento <coordinates> não encontrado no <Polygon> do KML.")

    coords_texto = coords_elem.text.strip()
    if not coords_texto:
        raise ValueError("Elemento <coordinates> do KML está vazio.")

    tokens = coords_texto.split()
    vertices: list[tuple[float, float]] = []

    for tok in tokens:
        tok = tok.strip()
        if not tok:
            continue
        partes = tok.split(",")
        if len(partes) < 2:
            raise ValueError(
                f"Coordenada KML malformada: '{tok}'. "
                "Esperado 'longitude,latitude' ou 'longitude,latitude,altitude'."
            )
        try:
            lon = float(partes[0])
            lat = float(partes[1])
        except (ValueError, TypeError) as e:
            raise ValueError(f"Coordenada numérica KML inválida: '{tok}'.") from e
        vertices.append((lon, lat))

    if not vertices:
        raise ValueError("Nenhum vértice pôde ser extraído do KML.")

    return vertices
