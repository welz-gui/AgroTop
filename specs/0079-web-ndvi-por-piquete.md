# Spec 0079 — Web: NDVI por piquete (satélite)

- **Tipo:** implementação · **Risco:** médio · **Esforço:** 2-3 dias
- **Branch:** `feat/web-ndvi-por-piquete`
- **Altere:** `services/ndvi.py` (novo), `app.py` (nova seção dentro de `page_lotes`),
  `requirements.txt` (uma dependência nova, ver abaixo), e os testes correspondentes
- **Pré-requisito:** [spec 0004 (PoC NDVI)](0004-poc-ndvi-viabilidade.md) — leia
  `poc/ndvi/README.md` inteiro antes de começar, é a fonte de todo número e decisão
  citados aqui — e Trilha 2 (`services/geometria.py`, `database.py::set_lote_poligono`),
  ambas já mescladas e em produção

---

## Regra de ouro desta spec (não negociável)

Duas frases do ROADMAP.md (Trilha 4) e do PoC (spec 0004) valem mais que qualquer
decisão de implementação abaixo:

> **"NDVI não equivale a kg de matéria seca — nenhum alerta deve afirmar disponibilidade
> de forragem sem calibração de campo."**

> **"Não coloque chave de API no código nem no commit. Use variável de ambiente."**

Nenhuma tela, texto, tooltip ou nome de campo desta feature pode sugerir "X kg de pasto
disponível", "forragem suficiente para N dias" ou qualquer conversão de NDVI em massa —
só o índice, sua série temporal, e a data/qualidade da imagem. Se o mecanismo escolhido
de acesso a dados precisar de credencial, ela vem de variável de ambiente
(`os.environ`), documentada no `.env.example`/README, nunca hardcoded nem commitada.

## O que a PoC (spec 0004) já decidiu — não redecida isto

A PoC rodou de ponta a ponta e concluiu, com números reais (`poc/ndvi/README.md`):

- **Fonte de dados: Earth Search v1 da Element 84** (`https://earth-search.aws.element84.com/v1`,
  coleção `sentinel-2-l2a`), lendo os COGs Sentinel-2 L2A do bucket público de Dados
  Abertos da AWS. **Não exige cadastro, plano pago nem chave de API** — não há segredo
  para gerenciar nesta integração específica. (A v0 do Earth Search está depreciada, não
  use.)
- **Limiar operacional: até 20% de nuvem por cena**, mascarando localmente com a banda
  SCL (classes de superfície 4/5/6/7 — vegetação, não-vegetação, água, neve; exclui
  nuvem/cirrus/sombra/saturação/nodata) antes de calcular o NDVI. Não use só
  `eo:cloud_cover` da cena inteira como filtro final — ele não garante que o *polígono*
  específico do piquete está livre de nuvem.
- **NDVI = `(B08 - B04) / (B08 + B04)`**, só nos pixels que sobrevivem à máscara SCL,
  bandas B04 (red) e B08 (nir) do Sentinel-2 L2A, aplicando escala/offset do metadado
  STAC.
- **Recomendação explícita da PoC: "Seguir com ressalvas"** — o sinal sazonal é real e
  informativo (amplitude observada de 0,45 no piquete de teste, com sequência coerente de
  perda/recuperação de vigor), mas **a cobertura de nuvem cria vãos longos na estação
  chuvosa** (maior vão de 105 dias a 20% de nuvem; meses de nov/dez/fev/mar podem não ter
  nenhuma cena utilizável). **Não prometa monitoramento contínuo nem alerta em tempo
  quase real durante a chuva** — é a condição que a PoC pôs para seguir.
- Revisita nominal do Sentinel-2 é de ~5 dias; na seca isso se traduziu em cena
  utilizável a cada ~5 dias no teste da PoC, e na chuva em ~53-106 dias dependendo do
  limiar — **use esses números para calibrar a expectativa mostrada ao usuário**, não
  prometa uma cadência fixa de atualização.

Se algo aqui parecer errado ou datado, releia `poc/ndvi/README.md` antes de divergir —
não decida contra o resultado registrado da PoC sem reabrir a pergunta explicitamente no
PR.

## Objetivo

Expor, por piquete (lote com `poligono` cadastrado via spec 0069/0070), a série temporal
de NDVI médio calculada a partir de Sentinel-2, com transparência sobre a data da última
imagem utilizável e o vão de dias sem cobertura — como uma leitura de tendência e
conferência periódica, não como monitoramento contínuo.

## Contexto que você precisa

- `database.py::get_lote(lote_id) -> Optional[dict]` devolve a linha crua da tabela
  `lotes`, incluindo `poligono` (texto GeoJSON ou `None`). Nem todo lote tem polígono
  cadastrado — **trate a ausência como "sem piquete demarcado ainda", não como erro**,
  mesmo tratamento que `page_lotes` já dá hoje (linha ~2036: `if not l.get("poligono")`).
- `app.py::_ler_poligono`/`_poligono_para_texto` (linhas ~5887-5921) já sabem parsear o
  formato de anel de coordenadas usado pelo resto do app — reuse-os para extrair o
  polígono do lote, não escreva um parser novo.
- `poc/ndvi/demo.py` é a implementação de referência (busca STAC, filtro de nuvem,
  máscara SCL, cálculo de NDVI, `largest_gap()`) — **porte a lógica de cálculo para
  `services/ndvi.py` como funções puras testáveis**, não reimplemente do zero e não
  importe o script da PoC diretamente (ele escreve CSVs/PNGs em disco, é uma ferramenta de
  investigação, não uma dependência de produção).
- `poc/ndvi/requirements.txt` usa `rasterio>=1.4.0` para ler os COGs — é a única
  dependência realmente nova desta spec (o resto — `requests`, `shapely` — já está em
  `requirements.txt` da raiz). `rasterio` traz binários nativos (GDAL); **adicione-o ao
  `requirements.txt` da raiz** e confirme no PR que a suíte de testes ainda instala e
  roda em CI com ele.

## Contrato obrigatório

### `services/ndvi.py` (novo módulo, funções puras)

```python
def ndvi_do_piquete(
    poligono: list[tuple[float, float]],
    inicio: date,
    fim: date,
    nuvem_max_pct: int = 20,
) -> NdviResultado:
    """Busca cenas Sentinel-2 (Earth Search v1) que cobrem `poligono` no período,
    filtra por `nuvem_max_pct`, calcula NDVI médio mascarado por SCL em cada cena
    utilizável. Devolve a série (pode ser vazia) mais o maior vão em dias — mesma
    definição de `largest_gap()` da PoC, incluindo bordas do período.
    """
```

- `NdviResultado`: dataclass com `serie: list[NdviPonto]` (cada um `data`, `ndvi_medio`,
  `nuvem_pct_cena`, `id_da_cena`), `maior_vao_dias: int`, `total_cenas_buscadas: int`,
  `total_cenas_utilizaveis: int`.
- Nenhuma cena utilizável no período → `NdviResultado` com `serie=[]`, não exceção — é um
  estado válido (idêntico ao "sem cena a este limiar" que a PoC documentou para
  nov/dez/fev/mar), a UI decide como mostrar.
- Erro de rede/timeout ao consultar o STAC → propague uma exceção clara
  (`NdviIndisponivelError` ou similar) que a UI web capture e mostre como "serviço de
  imagens indisponível agora, tente mais tarde" — **não deixe a página inteira quebrar**
  nem finja que é "sem cena".

### `app.py::page_lotes` — nova seção/aba

- Dentro da visão de um lote com `poligono` cadastrado (mesmo bloco onde hoje se edita o
  perímetro), adicione uma seção "🛰️ NDVI (satélite)" com:
  - Botão explícito para buscar/atualizar (não busque automaticamente a cada
    renderização — cada busca faz requisições de rede reais; trate como ação sob
    demanda, cacheável com `st.cache_data` por lote+período, mesmo padrão de cache já
    usado no resto do app).
  - Gráfico de série temporal do NDVI médio (`px.line`, mesma lib já usada em outros
    gráficos do app).
  - Data da imagem mais recente utilizável e o maior vão em dias, com um aviso visível
    quando o vão for grande (ex.: acima de ~60 dias) explicando que é esperado na
    estação chuvosa, não é falha do sistema.
  - **Um aviso permanente, sempre visível junto ao gráfico** (não escondido em tooltip):
    o texto da "Regra de ouro" desta spec, resumido — NDVI não é matéria seca, requer
    calibração de campo para virar decisão de forragem.
- Lote sem `poligono`: não mostre a seção, ou mostre um aviso "demarque o perímetro do
  piquete primeiro" com link/instrução para a UI de perímetro já existente — não invente
  um polígono aproximado.

## Critério de aceite

1. `services/ndvi.py` testado com STAC/COG mockados (não bata na rede real nos testes de
   CI) — cubra: cena(s) utilizável(is) simples, zero cenas utilizáveis no limiar, cálculo
   do maior vão incluindo as bordas do período (mesmo caso que a PoC corrigiu: vão do
   início do período até a primeira cena, e da última cena até o fim).
2. Erro de rede/STAC indisponível → `NdviIndisponivelError` (ou equivalente), testado.
3. `page_lotes`, lote sem `poligono` → seção de NDVI ausente ou com aviso de "demarque o
   perímetro primeiro", nunca crash.
4. O aviso "NDVI não equivale a matéria seca" está presente e visível no texto renderizado
   da seção — teste isso (grep no output/teste de UI), não confie só em revisão visual.
5. Nenhuma chave de API hardcoded — confirme com `grep -rn` que não há string parecida com
   token/key nova em `services/ndvi.py`/`app.py` (Earth Search v1 não exige uma, então o
   caso esperado é **nenhuma** variável de ambiente nova; se a implementação escolher
   outra fonte que precise de credencial, ela tem de vir de `os.environ`, documentada).
6. `flake8`/`ruff` e a suíte inteira (`AGROTOP_FORCE_SQLITE=1 python -m unittest discover
   -s tests -t . -v`) verdes, incluindo com `rasterio` instalado.

## Proibições

- ❌ Não escreva nem sugira nenhuma conversão de NDVI para "kg de matéria seca",
  "capacidade de suporte" ou "dias de pasto restante" — é a proibição central desta spec
  e do PoC que a precede.
- ❌ Não prometa (em texto de UI, docstring ou nome de variável) monitoramento contínuo,
  "tempo real" ou alerta automático de queda de NDVI — a PoC condicionou o "seguir" a
  isso explicitamente; se quiser propor alerta automático depois, é uma spec nova, com
  essa pergunta feita de propósito, não um acréscimo silencioso aqui.
- ❌ Não hardcode nem commite chave de API — releia ROADMAP R19.
- ❌ Não adicione NDVI ao app mobile (Flutter) nesta spec — ADR 0007 não cobre isso, e a
  PoC recomenda "com ressalvas" justamente pelo tipo de tela/gráfico que pede análise, não
  consulta rápida no campo; se fizer sentido depois, é uma spec de mobile separada,
  discutida à parte.
- ❌ Não use a v0 do Earth Search (`sentinel-s2-l2a-cogs`) — está depreciada, a PoC já
  confirmou que devolve cobertura incompleta.
- ❌ Não altere `services/geometria.py`, `database.py::set_lote_poligono` nem o fluxo de
  demarcação de perímetro (specs 0069/0070) — esta spec só consome o `poligono` já salvo.

## Como verificar antes de abrir o PR

```bash
pip install -r requirements.txt   # confirme que rasterio instala sem erro no ambiente de CI
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t . -v
python -m compileall app.py services
grep -rn "api_key\|API_KEY\|token.*=.*['\"]" services/ndvi.py   # confirme: nada hardcoded
```

## Entrega

PR para `main`, pronto para revisão. Confirme no corpo do PR que releu `poc/ndvi/README.md`
antes de implementar, que os testes de `services/ndvi.py` não fazem requisição de rede
real, e cole o texto exato do aviso "NDVI não equivale a matéria seca" como ele aparece
na UI.
