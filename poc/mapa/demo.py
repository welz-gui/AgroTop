"""Demo PoC: Desenho de Piquetes e Cálculo de Área no Streamlit."""

import folium
from folium.plugins import Draw
import pyproj
from shapely.geometry import shape
import streamlit as st
from streamlit_folium import st_folium

st.set_page_config(page_title="PoC Mapa de Piquetes", layout="wide")

st.title("🌾 PoC — Desenho de Piquetes e Cálculo de Área")
st.markdown(
    "Esta PoC demonstra o desenho interativo de polígonos (piquetes) sobre mapa de satélite "
    "usando `streamlit-folium`, com retorno de coordenadas em GeoJSON e cálculo geodésico de área."
)

# Centro padrão (exemplo: região agrícola de Mato Grosso)
CENTER_LAT = -12.5500
CENTER_LON = -55.7000

# Criar mapa Folium com camada de satélite
m = folium.Map(
    location=[CENTER_LAT, CENTER_LON],
    zoom_start=14,
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attr="Esri World Imagery",
)

# Adicionar controle de desenho (Leaflet.Draw)
draw = Draw(
    export=True,
    filename="piquete_desenhado.geojson",
    position="topleft",
    draw_options={
        "polyline": False,
        "circle": False,
        "circlemarker": False,
        "marker": False,
        "polygon": True,
        "rectangle": True,
    },
    edit_options={"edit": True, "remove": True},
)
draw.add_to(m)

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("Mapa Interativo (Desenhe o Piquete)")
    output = st_folium(m, width="100%", height=500, key="folium_map")

with col2:
    st.subheader("Dados Capturados")

    if output and output.get("all_drawings"):
        drawings = output["all_drawings"]
        st.success(f"Polígono(s) capturado(s): {len(drawings)}")

        geod = pyproj.Geod(ellps="WGS84")

        for idx, feature in enumerate(drawings, start=1):
            st.markdown(f"### Piquete #{idx}")
            geom = feature.get("geometry")

            if geom:
                shapely_geom = shape(geom)
                # Cálculo geodésico de área e perímetro
                area_m2, perimeter_m = geod.geometry_area_perimeter(
                    shapely_geom
                )
                area_m2 = abs(area_m2)  # Garantir valor positivo
                area_ha = area_m2 / 10000.0

                st.metric(
                    "Área Calculada",
                    f"{area_ha:.2f} ha",
                    delta=f"{area_m2:.1f} m²",
                )
                st.metric("Perímetro", f"{perimeter_m:.1f} m")

                with st.expander("Ver GeoJSON"):
                    st.json(feature)
    else:
        st.info(
            "Utilize as ferramentas de desenho no canto superior esquerdo do mapa para traçar um piquete."
        )
