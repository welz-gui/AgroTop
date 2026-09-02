# Spec 0069 — API: gravar perímetro do piquete a partir de uma lista de pontos

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** meio dia
- **Branch:** `feat/api-perimetro-por-pontos`
- **Altere:** só `backend_api/` (`main.py`, `schemas.py`) e os testes correspondentes
- **Pré-requisito:** nenhum — `database.py::set_lote_poligono` e
  `services/geometria.py` já existem, testados, em produção via o app web
  (ROADMAP Trilha 2, item 2, fechado em 2026-08-14).

---

## Regra de ouro desta spec

**Zero lógica nova.** O que `app.py::_render_tab_visao_geral` já faz ao salvar o
perímetro digitado — montar o GeoJSON, validar com `services/geometria.py::validar`,
gravar com `database.py::set_lote_poligono` (que deriva e grava `area_ha` na mesma
escrita) — esta spec só expõe em JSON, trocando "digitar vértices" por "uma lista de
pontos que o cliente já coletou" (a fonte, GPS ou texto, não importa pra esta API).

## Objetivo

Último item da Trilha 2 (ROADMAP §5, item 4): **demarcação por GPS caminhando o
perímetro**, no mobile. O piquete que nunca foi medido de verdade — só uma área
digitada de memória — passa a ter perímetro real, registrado por quem caminhou a
cerca. Esta spec cria a API; a spec mobile seguinte
([0070](0070-mobile-demarcacao-de-perimetro-por-gps.md)) coleta os pontos e chama
aqui.

## Contexto que você precisa

- **Validação — mesma sequência do web**, em `app.py::_render_tab_visao_geral`
  (busque por `🗺️ Perímetro do` para achar o trecho):
  1. Monta o anel: `anel = [(lon, lat), (lon, lat), ...]` a partir dos pontos
     recebidos.
  2. `problemas = services.geometria.validar(anel)` — devolve uma **lista de strings**
     (vazia = válido). Não invente formato de erro diferente, repasse essas
     mensagens.
  3. Só grava se `problemas` estiver vazia.
- **Gravação** — `database.py::set_lote_poligono(lote_id: str, poligono_geojson:
  Optional[str]) -> bool`. Espera uma **string GeoJSON já serializada**, não a lista
  de pontos — monte assim antes de chamar (mesmo formato do web):
  ```python
  poligono_geojson = json.dumps({
      "type": "Polygon",
      "coordinates": [[[lon, lat] for lon, lat in anel]],
  })
  ```
  A função já deriva e grava `area_ha` na mesma escrita — **não recalcule área
  nesta spec**, é `set_lote_poligono` quem faz isso via
  `services/geometria.py::area_hectares` internamente.
- **Mínimo de pontos** — `services/geometria.py::validar` já recusa polígonos com
  menos de 3 vértices distintos (parte da lista de `problemas`) — não adicione essa
  checagem de novo no endpoint, deixe a função pura recusar.
- **Piquete precisa existir** — `database.py::get_lote(lote_id)` (já usada em
  `backend_api/main.py`) devolve `None` se não existir. Confira antes de tentar
  gravar.

## Contrato obrigatório

```
POST /lotes/{lote_id}/perimetro
  body: { "pontos": [[lon, lat], [lon, lat], [lon, lat], ...] }
  -> 200: { "ok": true, "area_ha": float, "perimetro_m": float }
  -> 404: piquete não encontrado
  -> 422: polígono inválido — detail é a lista de mensagens de
     `services.geometria.validar` (auto-interceptante, menos de 3 pontos, etc.)
```

- `pontos` é `[longitude, latitude]` por item — mesma ordem GeoJSON/EPSG:4326 usada
  em todo o resto do projeto (`_ler_poligono` no web é explícito sobre isso: nunca
  aceitar as duas ordens, ambas são negativas no Brasil e a troca passa
  despercebida).
- `perimetro_m` na resposta vem de `services/geometria.py::perimetro_metros(anel)`
  — não é gravado no banco (só `area_ha` é persistido, mesmo comportamento do web),
  é só para o cliente mostrar de volta ao operador antes de confirmar.
- Autenticação igual às outras rotas de escrita (token válido, qualquer papel).
- **Sem `Idempotency-Key`** — mesmo padrão da spec 0067 (`POST /lotes`): fora do
  escopo da fila offline (ADR 0006 cobre só pesagem/medicamento/movimentação,
  spec 0060). Reenviar o mesmo perímetro é inofensivo — sobrescreve com o mesmo
  resultado, não duplica nada.

## Critério de aceite

1. `POST /lotes/{id}/perimetro` sem token → 401.
2. `lote_id` inexistente → 404.
3. Polígono válido (retângulo simples, 4+ pontos) → 200, `area_ha` bate com
   `services.geometria.area_hectares` calculado independentemente no teste, e
   `GET /lotes` (ou consulta direta) confirma que `lotes.area_ha` foi atualizado.
4. Polígono com menos de 3 pontos → 422, **não grava** (confirme que `poligono` do
   piquete não mudou).
5. Polígono auto-interceptante (gravata) → 422, **não grava**.
6. Perímetro salvo com sucesso é recuperável — `GET /lotes` ou uma nova
   `GET /lotes/{lote_id}/perimetro` (se você achar necessário adicionar; não é
   obrigatório nesta spec, `GET /lotes` já existe) mostra o resultado.
7. `flake8`/`ruff` e a suíte inteira de `tests/test_backend_api.py` verde.

## Proibições

- ❌ Não recalcule área ou perímetro fora de `services/geometria.py` — as funções
  puras já existem e já são a fonte de verdade usada pelo web.
- ❌ Não reimplemente a validação de polígono (auto-interceptante, poucos pontos)
  — `services.geometria.validar` já cobre.
- ❌ Não altere `app.py`, `database.py`, `services/`, `repositories/` nem as specs
  anteriores.
- ❌ Não invente suporte a multi-polígono ou buraco (`holes`) — o formato do
  projeto inteiro é um anel só, mesmo que o GeoJSON tecnicamente suporte mais.

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t . -v
python -m compileall backend_api tests
```

## Entrega

PR para `main`, pronto para revisão. Confirme no corpo que os 7 critérios têm teste
com prova real (não só "não deu erro") — mesmo padrão das specs 0054/0050/0063/0065/0067.
