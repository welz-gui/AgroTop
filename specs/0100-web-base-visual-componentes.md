# Spec 0100 — Web: escala tipográfica, espaçamento e variantes de componente

- **Tipo:** manutenção/implementação · **Risco:** médio · **Esforço:** 1-2 dias
- **Branch:** `feat/web-base-visual-componentes`
- **Altere:** `app.py` (bloco de CSS, linhas ~100-160), `tests/test_tema.py`, prova de UI
  dedicada
- **Pré-requisito:** [spec 0099](0099-web-formatacao-pt-br.md) (evita duas rodadas tocando
  as mesmas linhas de apresentação)

---

## Objetivo

RD04 da proposta de redesign (`DESIGN-IS-2026-09-10/proposta-specs-redesign-para-revisao-claude.md`)
— continuação direta da [spec 0091](0091-web-contraste-de-badges-e-css-em-tokens.md), que já
moveu todo o bloco de CSS para `var(--token)` mas manteve as escalas de tamanho/espaço/raio
de antes. As três imagens-conceito aprovadas pelo usuário (`DESIGN-IS-2026-09-10/propostas-web/`)
pedem hierarquia mais clara entre título, KPI e texto de apoio — hoje `.page-title` e
`div[data-testid="stMetricValue"]` usam o **mesmo tamanho** (`1.55rem`), sem diferenciação.

## Contexto que você precisa

- **`c = cores()` está duplicado** em `app.py` (duas linhas idênticas seguidas, logo depois
  de `db.refresh_carencia_status()`) — remova a linha redundante como parte desta spec
  (está exatamente no bloco que você vai editar; não abra um PR separado só para isto).
- **`primaryColor` do `.streamlit/config.toml` já é `#4ade80`**, idêntico a
  `ui/tema.py::ESCURO['primaria']` — os botões `st.button(type="primary"/"secondary")` já
  renderizam corretos nativamente, sem CSS customizado. **Não crie CSS novo para
  ação primária/secundária** — já funciona; a spec é sobre tamanho e espaçamento ao redor.
- **`tests/test_tema.py::test_todos_os_valores_sao_hex`** itera `tema.TEMAS.items()` e exige
  que **todo** valor seja hex de 6 dígitos — **não adicione valores de tipografia/espaçamento
  dentro de `ESCURO`/`CLARO`**, isso quebraria esse teste (e o gerador mobile, que só espera
  cor). Espaçamento e tipografia não variam por tema (claro/escuro têm o mesmo ritmo visual),
  então **não precisam vir de `cores()`** — defina como constantes CSS fixas, direto no bloco
  `<style>`, documentadas com um comentário curto explicando a escala escolhida.
- **Escala proposta** (a proposta original permite ajustar, desde que fixe uma escala única
  antes das telas seguintes — RD07/RD08/RD09 dependem desta):

  | Papel | Tamanho | Onde já existe hoje |
  |---|---|---|
  | Corpo | 15px (`.9375rem`) | Padrão do Streamlit, sem override hoje |
  | Apoio/legenda | 13px (`.8125rem`) | Novo, não existe hoje |
  | Seção | 19px (`1.1875rem`) | Novo, não existe hoje |
  | Título de página | 30px (`1.875rem`) | `.page-title`, hoje `1.55rem` (24,8px) |
  | KPI | 32px (`2rem`) | `stMetricValue`, hoje `1.55rem` (24,8px) — mesmo tamanho do título, sem diferenciação |
  | Espaçamento | 4/8/12/16/24/32px | Já usado de forma ad-hoc no CSS (`.5rem`, `1rem`, `1.2rem`, `1.5rem` — inconsistente); padronize para a escala de 8 valores |
  | Raio base | 12px | Já varia entre 8px/10px/14px/16px no bloco atual — padronize pra 12px, exceto badges (`999px`, pílula, mantém) |

## Contrato obrigatório

1. **`.page-title`**: `font-size: 1.875rem` (30px), mantém `font-weight:800` e
   `border-left`/`color: var(--primaria)`.
2. **`div[data-testid="stMetricValue"]`**: `font-size: 2rem` (32px) — agora maior que o
   título, reforçando que KPI é o dado mais importante da tela, coerente com as imagens
   aprovadas.
3. **Novas classes utilitárias** para os papéis que faltam, usadas onde apropriado nas telas
   seguintes (RD07/RD08/RD09 vão aplicá-las, esta spec só as define):
   ```css
   .texto-apoio{font-size:.8125rem;color:var(--texto_secundario)}
   .titulo-secao{font-size:1.1875rem;font-weight:700;color:var(--texto)}
   ```
4. **Raio unificado em 12px** nos seletores que hoje variam (`.stButton>button` 10px→12px,
   `div[data-testid="stMetric"]` 14px→12px, `.card`/`.card-*` 16px→12px, `.keypad-display`
   14px→12px) — badges continuam com `border-radius:999px` (formato pílula, não é raio de
   card).
5. **Espaçamento**: troque os valores ad-hoc de padding/margin no bloco por múltiplos da
   escala 4/8/12/16/24/32px mais próximos (ex.: `1.2rem` → `1rem` [16px] ou `1.5rem` [24px],
   o que for mais próximo visualmente — não precisa ser pixel-perfeito, precisa parar de ter
   um valor novo por seletor).
6. **Alvo de toque mínimo 48px** em botões usados nas telas de manejo (Modo Campo) — confirme
   que `.stButton>button{min-height:2.75rem}` (44px) já está perto; se qualquer botão de
   manejo usar um seletor diferente com altura menor, ajuste para `min-height:3rem` (48px).
7. **Foco visível**: confirme que `:focus-visible` em botões/inputs não fica invisível contra
   o fundo do tema escuro (Streamlit já cuida disso nativamente na maioria dos casos — só
   adicione CSS se um teste em navegador mostrar um caso real sem contorno de foco).

## Critério de aceite

1. Captura comparável antes/depois de uma tela com título + KPIs + card (ex. Dashboard),
   claro e escuro, mostrando a nova hierarquia de tamanho.
2. `_num_br`/`_data_br` (spec 0099, se já mesclada) continuam funcionando — esta spec não
   mexe em conteúdo, só em apresentação.
3. `python -m unittest tests.test_tema` continua 100% verde — nenhum valor não-hex
   introduzido em `ESCURO`/`CLARO`.
4. Prova de UI nova confirma que o CSS gerado contém as novas classes utilitárias e os
   tamanhos da tabela acima (mesmo padrão de `tests/test_tema.py::test_bloco_css_do_app_nao_tem_hex_literal`,
   adaptado para checar presença de string, não ausência de hex).
5. `c = cores()` aparece uma única vez no arquivo.

## Proibições

- ❌ Não extraia regra de negócio nenhuma — é só CSS/apresentação.
- ❌ Não reescreva `app.py` inteiro nem crie módulo novo de componentes — o bloco de CSS
  atual (herdado da 0091) já é o lugar certo.
- ❌ Não crie CSS customizado para botão primário/secundário — Streamlit já resolve nativo
  via `primaryColor` do `config.toml`.
- ❌ Não coloque tamanho de fonte/espaçamento dentro de `ui/tema.py::ESCURO`/`CLARO` — quebra
  o teste que exige hex puro e o gerador mobile.
- ❌ Não mude a paleta de cor (verde, neutros) — só escala de tamanho/espaço/raio.

## Como verificar antes de abrir o PR

```bash
$env:AGROTOP_FORCE_SQLITE = "1"
python -m unittest tests.test_tema
python -m unittest discover -s tests -t .
```

## Entrega

PR para `main`, pronto para revisão. Cole capturas antes/depois nos dois temas.
