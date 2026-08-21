# Spec 0046 — Localização por propriedade na previsão do tempo (função pura)

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 1 dia
- **Branch:** `feat/localizacao-por-propriedade-clima`
- **Crie:** `services/clima_adaptador.py` e `tests/test_clima_adaptador.py` — **arquivos novos**

---

## Regra de ouro desta spec

Você cria **arquivos novos**. **Não altere nenhum arquivo existente** — nem `app.py`, nem
`services/geometria.py`, nem `database.py`. Seu produto é uma função pura, testada, com
contrato fixo — o mantenedor liga à tela depois (R31).

## Decisão registrada (é o que faltava para esta tarefa virar spec)

Trilha 2 do [ROADMAP](../ROADMAP.md), item 3, ficava sem spec porque a granularidade da
previsão ("chamar a API de tempo uma vez por piquete tem custo — decisão de UX/API ainda em
aberto") não tinha sido decidida. **Está decidida agora:**

**A previsão passa a ser por PROPRIEDADE, nunca por piquete.** Não por limite de custo da
API — `_fetch_forecast` usa o **Open-Meteo, gratuito e sem chave** (`app.py`, já em
produção), então não há cobrança por chamada a evitar. A razão é outra:

1. **Piquetes da mesma propriedade ficam geograficamente perto** — a diferença de previsão
   entre eles não é significativa o bastante para justificar N cartões de previsão quase
   idênticos numa fazenda com dezenas de piquetes. Isso é ruído, não informação.
2. **Propriedades diferentes podem ficar longe de verdade** — a hierarquia
   Organização→Produtor→**Propriedade** (ADR 0004) já existe exatamente para o caso de um
   produtor com mais de uma fazenda, possivelmente em municípios diferentes. É aí que uma
   previsão distinta agrega valor real.
3. **O dado já existe e já é populado**: `properties.longitude`/`properties.latitude` são
   preenchidos por `services.geometria.centroide()` desde a spec 0015 — não falta coluna,
   não falta cálculo, falta só **usar** essa coordenada na previsão em vez da única
   coordenada `farm_lat`/`farm_lon` (`page_clima`, hoje "a mesma previsão vale para todos os
   piquetes da fazenda").

O que falta, e que **não é trivial o bastante para ser "só chamar `_fetch_forecast` nas
coordenadas da propriedade"**, é resolver de onde vem a coordenada de cada propriedade
(pode não ter a própria ainda) sem **duplicar chamada** para propriedades que caem no mesmo
fallback — é exatamente o contrato desta spec.

## Contexto que você precisa

- `repositories/propriedades.py::listar()` devolve `list[dict]` com pelo menos
  `id`, `nome`, `longitude`, `latitude` (mais campos que você ignora).
- `app.py::_fetch_forecast(lat, lon)` já existe, tem cache de 1h por par `(lat, lon)`
  (`st.cache_data(ttl=3600)`) — **você não recria nem toca nessa função**; o mantenedor
  troca a chamada única de hoje por um laço sobre o resultado do que você entregar.
- `db.get_setting("farm_lat")`/`"farm_lon"` são o fallback atual (única coordenada da
  fazenda, usada quando não há nada mais específico).

## Contrato obrigatório

```python
def localizacoes_para_previsao(
    propriedades: list[dict],
    farm_lat: float | None,
    farm_lon: float | None,
) -> list[dict]:
    """Uma entrada por LOCALIZAÇÃO DISTINTA a buscar a previsão — nunca uma
    por propriedade.

    Cada propriedade usa, nesta ordem: 1) sua própria
    `longitude`/`latitude`, se ambas presentes; 2) o fallback
    `farm_lat`/`farm_lon`, se presentes; 3) se nem isso houver, a
    propriedade fica de fora do resultado (não há onde buscar previsão —
    isso não é um erro, é um estado válido para quem ainda não configurou
    nada).

    Duas ou mais propriedades que resolvem para a MESMA coordenada (seja
    porque compartilham a própria, seja porque as duas caem no mesmo
    fallback) geram UMA única entrada, agrupadas — evita chamar
    `_fetch_forecast` duas vezes para o mesmo lugar.

    `propriedades`: [{"id": str, "nome": str,
                       "longitude": float | None, "latitude": float | None}, ...]
                     (aceita o dict completo de `repositories.propriedades.listar()`
                     — usa só esses quatro campos, ignora o resto)

    Retorna, na ordem de primeira ocorrência das propriedades na lista de entrada:
        [{"lat": float, "lon": float,
          "propriedades": [{"id": str, "nome": str}, ...]}, ...]
    """
```

**Assine exatamente assim.**

## Critério de aceite

1. Propriedade com `longitude`/`latitude` próprias usa essas coordenadas, **não** o
   fallback — mesmo que o fallback também esteja presente.
2. Propriedade sem coordenada própria (`None` em qualquer uma das duas) usa
   `farm_lat`/`farm_lon`.
3. Duas propriedades sem coordenada própria — ambas caindo no mesmo fallback — geram **uma
   única entrada**, com as duas listadas em `"propriedades"`.
4. Duas propriedades com coordenadas próprias **idênticas** também geram uma única entrada
   (mesmo raciocínio do item 3, fonte diferente).
5. Propriedade sem coordenada própria **e** sem fallback (`farm_lat`/`farm_lon` também
   `None`) não aparece em nenhuma entrada do resultado — e não gera entrada com `lat`/`lon`
   `None`.
6. Lista de propriedades vazia devolve lista vazia, sem lançar exceção mesmo com
   `farm_lat`/`farm_lon` ausentes.
7. A ordem do resultado é determinística: a primeira propriedade da lista de entrada cujo
   par de coordenadas aparece define a posição do grupo no resultado (prova com uma lista
   de propriedades em ordem específica e conferindo a ordem de saída).

## Proibições

- ❌ Não toque em `app.py`, `database.py`, `services/geometria.py`,
  `repositories/propriedades.py` nem em qualquer outro módulo existente.
- ❌ Não chame `_fetch_forecast` nem faça requisição HTTP nenhuma — esta função só decide
  **quais** coordenadas buscar, nunca busca.
- ❌ Não implemente agrupamento por proximidade geográfica (ex.: "propriedades a menos de
  5 km uma da outra compartilham previsão") — **fora de escopo desta spec**. O agrupamento
  aqui é só por coordenada **idêntica** (mesmo valor, não "parecido"); geoespacial
  aproximado é problema mais caro e não está justificado pelo volume esperado de
  propriedades por produtor.
- ❌ Não adicione dependência nova — a função é aritmética simples sobre dicts.
- ❌ Não integre à tela `page_clima`. Isso é do mantenedor.

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t .
python -m compileall services tests
git diff --stat origin/main
```

O `-t .` não é opcional (R16). No diff, só os dois arquivos novos.

## Entrega

PR para `main`, pronto para revisão. No corpo, mostre o caso do critério de aceite 3 e 4
lado a lado — é o que prova que o agrupamento funciona pelas duas origens possíveis de
coordenada idêntica (fallback compartilhado e coordenada própria compartilhada).
