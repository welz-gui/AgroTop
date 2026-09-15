# Spec 0108 — Mobile: dashboard compacta indicadores sem perder nenhum

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** meio dia
- **Branch:** `feat/mobile-dashboard-compacto-e-grafico`
- **Altere:** `mobile/lib/screens/dashboard_resumo_page.dart`,
  `mobile/test/dashboard_resumo_page_test.dart`, goldens correspondentes
- **Pré-requisito:** [spec 0101](0101-mobile-dashboard-estado-desatualizado.md) (RD02,
  mesclada) — o banner de dados desatualizados precisa continuar visível na composição final

---

## Objetivo

RD11 da proposta de redesign (`DESIGN-IS-2026-09-10/proposta-specs-redesign-para-revisao-claude.md`).
O dashboard mobile (`dashboard_resumo_page.dart`) já recebeu boa parte do trabalho que a
proposta original pedia (alertas antes dos indicadores via spec 0093, grid de 2 colunas já
existente) — o que sobra é bem mais estreito do que o RD11 original descrevia.

## Contexto que você precisa

- **Estado já bem mais avançado do que a proposta original presumia** (a evidência da
  proposta aponta pra uma versão anterior do código) — confirme antes de "recriar" o que já
  existe:
  - Alertas **já aparecem antes** dos indicadores (`dashboard_resumo_page.dart:169-196`,
    spec 0093).
  - Os 7 indicadores **já estão em grid de 2 colunas** (`GridView.count(crossAxisCount: 2,
    childAspectRatio: 1.4, ...)`, `dashboard_resumo_page.dart:203-213`), não em coluna única
    como a proposta descrevia.
  - O gráfico de raça (`_BreedDonutChart`, `dashboard_resumo_page.dart:223-281`) **já lista
    todas as categorias na legenda** (`entries.asMap().entries.map(...)`,
    `dashboard_resumo_page.dart:253-275`) — nenhuma raça é omitida silenciosamente hoje.
  - O banner de dados desatualizados (spec 0101/RD02) já existe — confirme que ele continua
    renderizado **antes** de "Alertas" na composição depois desta spec (a 0101 o coloca entre
    `AppBar` e conteúdo; não regrida isso).
- **O que realmente falta** (comparado à composição da proposta):
  1. Machos e Fêmeas são dois `_MetricCard`s separados no grid (`dashboard_resumo_page.dart:
     160-161`) — a proposta pede uma única seção de composição (ex. "♂ 12 · ♀ 8" num só card,
     ou lado a lado dentro do mesmo espaço de grid) em vez de dois cards de 1/7 do grid cada.
  2. `_BreedDonutChart`/`_BreedDonutPainter` (`dashboard_resumo_page.dart:283-313`) não tem
     nenhum rótulo semântico (`Semantics`) para leitor de tela — a legenda textual abaixo já
     ajuda, mas o desenho em si (`CustomPaint`) é invisível para acessibilidade. Adicione um
     resumo textual (`Semantics(label: ...)`) cobrindo o que o gráfico mostra (ex. "Gráfico de
     distribuição por raça: Nelore 40%, Angus 30%, ...").
  3. Confirme que "Lotação" e "Arrobas produzidas" têm apresentação visualmente mais discreta
     que os 4 indicadores centrais (Total, Peso médio, GMD médio, Machos/Fêmeas), já que a
     proposta pede menor peso visual para eles sem removê-los — hoje todos os 7 cards do grid
     têm o mesmo estilo (`_MetricCard`, `dashboard_resumo_page.dart:323-344`).

## Contrato obrigatório

1. Machos e Fêmeas: uma composição única (card único com os dois valores, ou layout
   equivalente) — ambos os números continuam visíveis e legíveis, com seus `ValueKey`s atuais
   preservados (`dashboard-kpi-machos`/`dashboard-kpi-femeas`) ou substituídos por uma chave
   nova documentada no PR, desde que o teste correspondente seja atualizado junto.
2. `_BreedDonutChart` ganha `Semantics` com resumo textual da distribuição — sem remover a
   legenda existente (ela já é acessível via texto simples).
3. Lotação e Arrobas produzidas recebem apresentação secundária (fonte menor, ou fora do grid
   principal, à sua escolha) — os dois continuam presentes e com o mesmo valor calculado.
4. Nenhuma das 7 métricas originais desaparece — a mudança é só de composição/agrupamento.
5. Banner de estado desatualizado (spec 0101) continua no topo, antes de "Alertas".

## Critério de aceite

1. Todos os 7 valores (total, peso médio, GMD médio, arrobas, lotação, machos, fêmeas)
   continuam acessíveis na árvore de widgets, com os mesmos valores da base.
2. Largura 320px e escala de texto ampliada não cortam nenhum card do novo agrupamento.
3. Estado desatualizado do RD02 (spec 0101) permanece visível na posição correta.
4. Tocar em cada categoria de alerta continua abrindo o filtro correto (regressão da spec
   0097, sem mudança de comportamento aqui).
5. Dashboard vazio, com uma única raça e com falha de refresh continuam funcionando sem
   regressão (testes existentes).
6. Medição de altura do grupo de indicadores antes/depois com a mesma massa de dados de teste,
   mostrando redução real.

## Proibições

- ❌ Não remova nenhum dos 7 indicadores nem simplifique o cálculo de nenhum.
- ❌ Não recrie o que já está feito (alertas antes dos indicadores, grid de 2 colunas, legenda
   completa) — confirme o estado atual antes de escrever código, conforme o Contexto acima.
- ❌ Não adicione CTA de cadastro sem confirmar que o perfil atual tem permissão para a ação —
  se não tiver, explique o próximo passo real em vez de esconder ou mostrar botão sem handler.
- ❌ Não troque o `CustomPainter` do gráfico por uma lib nova — reuse o existente.

## Como verificar antes de abrir o PR

```bash
cd mobile
flutter analyze
flutter test test/dashboard_resumo_page_test.dart
CAPTURE_GOLDENS=1 flutter test --update-goldens
```

## Entrega

PR para `main`, pronto para revisão. Capturas antes/depois com dados normais, vazio, muitos
nomes de raça e falha de refresh; medição de altura do bloco de indicadores.
