# Spec 0107 — Mobile: métricas da ficha adaptam à largura real, com prioridade visual

- **Tipo:** implementação · **Risco:** médio · **Esforço:** 1 dia
- **Branch:** `feat/mobile-ficha-metricas-responsivas`
- **Altere:** `mobile/lib/screens/animals_page.dart` (`MetricCard` e a `Wrap` que a usa),
  `mobile/test/flow_test.dart`, golden `03-ficha`
- **Pré-requisito:** [spec 0104](0104-mobile-ficha-overflow-telas-pequenas.md) (corrige o
  overflow real já encontrado no cabeçalho/card de carência da mesma tela — implemente
  0104 primeiro para não competir no mesmo arquivo por causa parecida)

---

## Objetivo

RD10 da proposta de redesign (`DESIGN-IS-2026-09-10/proposta-specs-redesign-para-revisao-claude.md`).
`MetricCard` (`mobile/lib/screens/animals_page.dart:1124-1155`) usa largura fixa de 170px
dentro de um `Wrap` (`animals_page.dart:1001-1031`) — as 5 métricas (peso atual, peso de
entrada, GMD recente, GMD total, peso-alvo) têm o mesmo peso visual, sem diferenciar as que
importam mais para decisão de manejo (peso atual, GMD recente, meta) das de contexto (peso de
entrada, GMD total).

## Contexto que você precisa

- **Não é a mesma spec que a 0104** — a 0104 corrige overflow real (`RenderFlex overflowed`)
  no cabeçalho e no card de carência, achado pela spec 0096. Esta spec (0107) é sobre as 5
  `MetricCard`s especificamente: distribuição de largura e diferenciação de prioridade. Não
  duplique o trabalho — confirme que 0104 já foi mesclada antes de começar.
- **UUID/dados cadastrais já estão separados**, ao contrário do que a proposta original
  presumia: `animals_page.dart:1034-1061` já tem um `Card` próprio (Nascimento/Entrada/
  Fornecedor/UUID) **depois** das `MetricCard`s, não misturado com elas. **Não repita esse
  trabalho** — a proposta citava isso como problema, mas já está resolvido.
- **`MetricCard`** (`animals_page.dart:1124-1155`): `SizedBox(width: 170)` fixo, `Card` com
  ícone + label (`labelLarge`) + valor (`titleMedium`), todos do mesmo tamanho visual
  independente da métrica.
- **`Wrap`** (`animals_page.dart:1001-1031`, `spacing: 12, runSpacing: 12`) deixa o número de
  colunas por linha implícito (depende de quantos cards de 170px cabem) — em 320px só cabe 1,
  em 430px cabem 2, sem controle explícito de "uma coluna quando necessário, duas quando
  couber" como a proposta pede.

## Contrato obrigatório

1. Troque a largura fixa de `MetricCard` por uma distribuição que usa a largura real
   disponível — via `LayoutBuilder`/`GridView`/`Wrap` com `width` calculado
   (`(constraints.maxWidth - spacing) / colunas`), não mais um número mágico de 170.
2. **Duas colunas quando o texto e valores couberem sem cortar, uma coluna quando não couber**
   — defina o critério por largura disponível (ex. `constraints.maxWidth < 340 ? 1 : 2`,
   ajuste o limiar ao testar nas 4 larguras de referência) ou por medição real do conteúdo;
   documente a escolha no PR.
3. **Prioridade visual**: peso atual, GMD recente e peso-alvo (as três métricas de decisão de
   manejo) em destaque (ex. `titleLarge`/cor primária); peso de entrada e GMD total em
   contexto secundário (ex. `bodyMedium`/cor secundária) — sem remover nenhuma das 5.
4. Altura do `MetricCard` deixa de ser implícita ao conteúdo com `Column` simples e passa a
   acomodar `TextScaler` grande sem cortar (mesma verificação de overflow que a 0096/0104 já
   fazem, aplicada aqui às `MetricCard`s especificamente).
5. Preserve a ordem de ações definida na spec 0092 (`open-weighing`/`open-medication`/
   `open-movement`) e o bloco de dados cadastrais/foto/histórico já existente — esta spec só
   toca as `MetricCard`s e o `Wrap` que as contém.

## Critério de aceite

1. Larguras 320/360/390/430px e tablet 600px; escalas de texto 1.0/1.3/2.0 — nenhuma
   combinação produz overflow, corte ou sobreposição nas `MetricCard`s (mesma metodologia da
   spec 0096, aplicada às métricas).
2. ID longo, fornecedor longo, valor grande (`999.9 kg`) e valor ausente (`N/A`/traço) — todos
   cabem sem cortar.
3. As 5 métricas continuam presentes e com os mesmos `ValueKey`s/valores calculados no
   servidor — nenhuma foi removida ou recalculada no cliente.
4. Peso atual/GMD recente/peso-alvo visivelmente mais destacados que peso de entrada/GMD total
   (diferença de tamanho de fonte ou cor, verificável em captura).
5. Ordem de ações da spec 0092 e o resto da ficha (fotos, histórico, carência) sem mudança.

## Proibições

- ❌ Não recalcule métricas no cliente nem mude o que cada uma significa.
- ❌ Não remova nenhuma das 5 métricas nem troque `ValueKey`s dos fluxos existentes.
- ❌ Não oculte a ação de pesagem em menu de overflow.
- ❌ Não reduza fonte automaticamente a ponto de prejudicar leitura — se o conteúdo não
  couber, mude o layout (colunas/altura), não apenas encolha o texto.
- ❌ Não repita a remoção de texto técnico (isso é escopo da spec 0098/RD03, já mesclada) nem
  mexa no bloco de dados cadastrais (já está correto, ver Contexto acima).

## Como verificar antes de abrir o PR

```bash
cd mobile
flutter analyze
flutter test test/flow_test.dart test/offline_flow_test.dart
CAPTURE_GOLDENS=1 flutter test --update-goldens test/golden_screens_test.dart
```

## Entrega

PR para `main`, pronto para revisão. Capturas nas 4 larguras + tablet, com e sem escala de
texto ampliada, mostrando a diferenciação de prioridade entre métricas.
