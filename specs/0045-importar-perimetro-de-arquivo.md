# Spec 0045 — Importar perímetro de piquete de um arquivo (GeoJSON/KML) — função pura

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 1 dia
- **Branch:** `feat/importar-perimetro-de-arquivo`
- **Crie:** `services/importacao_geometria.py` e `tests/test_importacao_geometria.py` —
  **arquivos novos**

---

## Regra de ouro desta spec

Você cria **arquivos novos**. **Não altere nenhum arquivo existente** — nem `app.py`, nem
`services/geometria.py`, nem `database.py`. Seu produto é conversão de formato pura,
testada, com contrato fixo — o mantenedor liga à tela depois (R31).

## Objetivo

Trilha 2 do [ROADMAP](../ROADMAP.md), item 1 — prioridade **alta**. Hoje o perímetro de um
piquete só entra **digitando vértices**, um por linha, no formato `longitude, latitude`
(`app.py::_ler_poligono`). Quem já tem um arquivo `.geojson` ou `.kml` do piquete (comum em
quem já usa QGIS, Google Earth ou app de GPS de campo) precisa abrir o arquivo e copiar
número por número à mão. Esta spec entrega o **parser**; o "importar arquivo" da tela
(upload + botão) é integração e fica com o mantenedor, como sempre (R31).

**Não confunda com "desenhar no mapa"** — essa é outra funcionalidade (um componente de
mapa interativo tipo `streamlit-folium` com plugin de desenho), fora do escopo desta spec.

## Contexto que você precisa

`services/geometria.py` (spec 0015, já entregue) espera o perímetro como
`list[tuple[float, float]]` — pares `(longitude, latitude)` em graus (EPSG:4326), na ordem
do polígono. `app.py::_ler_poligono` lê esse mesmo formato de um textarea. **O contrato desta
spec é produzir exatamente essa mesma lista**, a partir do conteúdo de um arquivo, para que o
mantenedor possa alimentar `geometria.validar()`/`geometria.area_hectares()` sem nenhuma
conversão extra.

## Contrato obrigatório

```python
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

def ler_kml(conteudo: str) -> list[tuple[float, float]]:
    """Extrai o anel de vértices do primeiro `<Polygon>` de um KML.

    Lê `<outerBoundaryIs><LinearRing><coordinates>`. O KML aceita
    coordenadas com altitude (`lon,lat,alt`) separadas por espaço ou quebra
    de linha — descarte a altitude, ela não é usada em nenhum cálculo do
    módulo `geometria`.

    Levanta `ValueError`, com mensagem em português, se: o XML é inválido,
    não há nenhum `<Polygon>`, ou as coordenadas estão malformadas.
    """
```

**Assine exatamente assim.** Ambas devolvem `[(lon, lat), ...]` — o mesmo formato que
`services/geometria.py` já consome. **Nenhuma das duas valida geometria** (auto-interseção,
área zero etc.) — isso já existe em `geometria.validar()` e não deve ser duplicado (R8);
esta spec só converte formato de arquivo para a lista de vértices.

## Critério de aceite

1. GeoJSON com uma geometria `Polygon` "nua" (`{"type":"Polygon","coordinates":[[...]]}`)
   é lido corretamente.
2. GeoJSON `Feature` envolvendo essa mesma geometria (`{"type":"Feature","geometry":{...}}`)
   também é lido — é o formato mais comum de exportação real (QGIS, geojson.io).
3. GeoJSON `FeatureCollection` com um `Feature` de polígono é lido a partir do primeiro
   `Feature`.
4. GeoJSON `MultiPolygon` levanta `ValueError` — não escolhe "o primeiro" silenciosamente.
5. KML com `<Polygon><outerBoundaryIs><LinearRing><coordinates>` (coordenadas separadas por
   espaço, formato real exportado pelo Google Earth) é lido corretamente, com altitude
   presente e ignorada.
6. Conteúdo que não é JSON/XML válido levanta `ValueError` com mensagem em português —
   nunca devolve lista vazia silenciosamente (lista vazia pareceria "arquivo sem piquete
   nenhum", quando na verdade o arquivo está corrompido ou é de outro formato).
7. O resultado de `ler_geojson`/`ler_kml` alimentado direto em
   `services.geometria.validar()` não levanta exceção de formato — só, no máximo, os
   problemas geométricos que `validar()` já sabe detectar (prova de que os dois módulos
   encaixam sem conversão intermediária).

## Proibições

- ❌ Não toque em `app.py`, `database.py`, `services/geometria.py` nem em qualquer outro
  módulo existente.
- ❌ Não valide geometria (auto-interseção, vértices insuficientes, coordenada fora de
  faixa) — isso é `geometria.validar()`, não duplique.
- ❌ Não use nenhuma biblioteca nova. GeoJSON é JSON puro (`json`, da biblioteca padrão) e
  KML é XML (`xml.etree.ElementTree`, também padrão) — **não adicione dependência** ao
  `requirements.txt` da raiz para isto.
- ❌ Não integre a upload de arquivo nem a nenhuma tela — isso é do mantenedor.
- ❌ Não crie suporte a Shapefile (`.shp`) nesta spec — formato binário multi-arquivo,
  exigiria dependência nova (`pyshp`/`fiona`); fica para uma spec futura se for pedido.

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t .
python -m compileall services tests
git diff --stat origin/main
```

O `-t .` não é opcional (R16). No diff, só os dois arquivos novos.

## Entrega

PR para `main`, pronto para revisão. No corpo, cole um exemplo real de GeoJSON e de KML que
você usou no teste — ajuda o mantenedor a confirmar que os formatos testados são os que
ferramentas reais exportam, não uma versão simplificada demais.
