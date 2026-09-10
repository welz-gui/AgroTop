# Spec 0086 — Mobile: gráfico de rosca por raça no dashboard resumo

- **Tipo:** implementação · **Risco:** médio · **Esforço:** 1-2 dias
- **Branch:** `feat/mobile-grafico-raca-dashboard`
- **Altere:** `mobile/lib/screens/dashboard_resumo_page.dart`, `mobile/lib/models.dart`,
  `mobile/tool/generate_app_colors.py`, `mobile/lib/app_colors.dart` (regenerado, não
  editado à mão), e os testes/goldens correspondentes. **Nenhuma dependência nova** no
  `pubspec.yaml`
- **Pré-requisito:** [spec 0085](0085-api-distribuicao-por-raca-no-dashboard-resumo.md)
  (API) — precisa estar mesclada e em produção antes desta

---

## Regra de ouro desta spec

[ADR 0007 §5](../docs/adr/0007-escopo-de-paridade-admin-no-mobile.md) (emenda de
2026-09-10) libera **um** gráfico leve — sem zoom, sem hover, sem múltiplas séries — no
dashboard resumo do mobile. Esta spec é esse gráfico, e só ele. Não é a porta de entrada
para trazer todo o dashboard completo do web (GMD por animal, evolução de peso,
conformidade continuam fora).

## Objetivo

Desenhar a distribuição de animais por raça (spec 0085) como um gráfico de rosca no
`DashboardResumoPage` — o mesmo dado que `app.py::_dash_chart_por_raca` já mostra no
dashboard web, adaptado pra tela pequena.

## Contexto que você precisa

- **Sem biblioteca de gráfico nova.** O Flutter SDK já tem `CustomPainter`/`Canvas`
  (`dart:ui`), suficiente para um anel com fatias proporcionais — não traga
  `fl_chart`/`syncfusion`/similar só para isto. Mantém controle total sobre as cores
  (tokens do `AppColors`) sem lutar com a API de tema de uma lib de terceiro.
- **`ui/tema.py::SERIES`** (10 cores) é a paleta categórica que o web já usa em gráfico
  com várias fatias/séries (`color_discrete_sequence=SERIES` em `_dash_chart_por_raca`).
  **Hoje ela não existe em `app_colors.dart`** — precisa estender
  `mobile/tool/generate_app_colors.py` para também emitir `AppColors.series` (uma
  `List<Color>`, mesma ordem de `ui/tema.py::SERIES`), regenerar o arquivo, e confiar no
  check de CI já existente ("app_colors.dart não diverge de ui/tema.py") pra garantir que
  não diverge depois. **Não hardcode uma lista de cor separada no Dart** — quebraria a
  regra do `DESIGN.md` ("gerado a partir desta paleta, nunca escrito à mão") e não teria
  CI travando divergência.
- **`DashboardResumo.fromJson`** (`mobile/lib/models.dart`, linha ~505) — adicione um
  campo `distribuicaoPorRaca: List<RacaContagem>`, parseado de
  `json['distribuicao_por_raca']`. Nova classe pequena:
  ```dart
  class RacaContagem {
    const RacaContagem({required this.raca, required this.quantidade});
    final String raca;
    final int quantidade;
    factory RacaContagem.fromJson(Map<String, dynamic> json) => RacaContagem(
      raca: json['raca'] as String,
      quantidade: (json['quantidade'] as num).toInt(),
    );
  }
  ```
- **`DashboardResumoPage`** já busca o resumo via `widget.api.getDashboardResumo()`
  (`mobile/lib/api_client.dart`) — o parsing muda (novo campo), a chamada em si não.
- **Espaço de tela pequeno**: não tente rótulo dentro da fatia (ilegível numa tela de
  celular com várias raças pequenas) — desenhe o anel simples e uma **legenda em lista
  abaixo** (cor + nome da raça + quantidade), mesmo raciocínio de "nada essencial
  escondido" do `DESIGN.md` §6.
- **Rebanho sem animal, ou `distribuicao_por_raca` vazia** — não desenhe um anel vazio
  (visualmente quebrado); mostre texto simples ("Sem animais cadastrados ainda" — já
  existe tratamento parecido em `_EmptyDashboard`, reuse o padrão).

## Contrato obrigatório

- Novo widget privado `_BreedDonutChart` (ou nome equivalente) em
  `dashboard_resumo_page.dart`:
  - Recebe `List<RacaContagem>`.
  - `CustomPainter` desenhando um anel (`strokeWidth` fixo, não preenchido — mesmo
    visual de "rosca" que o web usa com `hole=0.45`) com uma fatia por raça, cor
    ciclando por `AppColors.series` na ordem em que as raças chegam (já vêm ordenadas
    por quantidade decrescente, spec 0085).
  - Legenda abaixo do anel: uma linha por raça, quadrado de cor + `"{raça} ({quantidade})"`.
  - Tamanho compacto — cabe junto dos cards de métrica já existentes, sem exigir rolagem
    maior que a tela atual já tem.
- Inserido em `_DashboardContent` (mesmo arquivo), depois da seção "Indicadores do
  rebanho" e antes de "Alertas" — mesma posição relativa que o web usa (raça vem logo
  depois dos KPIs).
- `distribuicao_por_raca` vazia → não renderiza o widget do gráfico, sem erro.

## Critério de aceite

1. `RacaContagem.fromJson` testado com payload real da spec 0085.
2. `_BreedDonutChart` com 3+ raças renderiza sem erro nos três temas (escuro/claro/
   sistema) — teste de widget, não precisa golden pixel-perfeito da forma do anel, mas
   confirme que os textos da legenda aparecem (`find.text('{raça} ({quantidade})')`).
3. `distribuicao_por_raca` vazia → nenhum erro, gráfico não aparece, resto da tela
   continua normal.
4. `AppColors.series` gerado corretamente por `generate_app_colors.py`, mesma ordem e
   mesmas 10 cores de `ui/tema.py::SERIES` — teste comparando as duas listas (mesmo
   padrão do check de CI para os tokens semânticos).
5. Golden de `dashboard_resumo_page` (se já existir suite própria, ou a tela dentro de
   `golden_screens_test.dart`) regenerado nos três temas — cole a saída do
   `--update-goldens` no PR.
6. `flutter analyze` limpo.

## Proibições

- ❌ Não adicione dependência de gráfico ao `pubspec.yaml` — `CustomPainter` já resolve.
- ❌ Não hardcode cor no Dart para a paleta de série — só via `AppColors.series` gerado.
- ❌ Não adicione interação (zoom, tooltip ao toque, animação de entrada elaborada) — é
  o "sem hover, sem zoom" que a emenda da ADR 0007 exigiu para não virar o dashboard
  completo.
- ❌ Não traga nenhum outro gráfico nesta spec (GMD por animal, evolução de peso) — só a
  distribuição por raça. Outro gráfico é spec nova, com a mesma pergunta feita de
  propósito sobre caber numa tela pequena.
- ❌ Não altere `backend_api/` — esta spec só consome o que a 0085 já expõe.

## Como verificar antes de abrir o PR

```bash
python mobile/tool/generate_app_colors.py
cd mobile
flutter analyze
flutter test
CAPTURE_GOLDENS=1 flutter test --update-goldens
```

## Entrega

PR para `main`, pronto para revisão. Confirme no corpo do PR que partiu da spec 0085 já
mesclada, e cole a saída do `generate_app_colors.py` mostrando `AppColors.series` gerado
corretamente.
