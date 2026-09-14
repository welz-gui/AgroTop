# Spec 0093 — Mobile: dashboard mostra alertas antes dos indicadores, tocáveis

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 1 dia
- **Branch:** `feat/mobile-dashboard-alertas-antes-e-tocaveis`
- **Altere:** `mobile/lib/screens/dashboard_resumo_page.dart`,
  `mobile/lib/screens/alerts_page.dart`, testes/goldens correspondentes
- **Pré-requisito:** nenhum

---

## Objetivo

Achado da auditoria de design (`DESIGN-IS-2026-09-10/03-verdict.md`, item #3, evidência
`dashboard_resumo_page.dart:107-175/227-235`): o dashboard mobile mostra sete métricas de
indicadores **antes** da seção de alertas, e os cards de alerta (Sumidos/Em carência/
Prontos para abate) só exibem uma contagem — tocar neles não faz nada. O parecer pede duas
coisas: (1) alertas acionáveis antes dos indicadores secundários, (2) abrir a lista
filtrada a partir do card.

## Contexto que você precisa

- **Ordem atual de `_DashboardContent.build`**: título "Indicadores do rebanho" → grade de
  7 `_MetricCard`s → gráfico de raça (se houver, spec 0086) → título "Alertas" → três
  `_AlertCountCard`s (sumidos/carência/prontos). Objetivo: inverter — Alertas primeiro,
  Indicadores (com o gráfico de raça) depois.
- **`_AlertCountCard`** (linha ~318) é hoje um `Card`+`ListTile` sem `onTap` — precisa
  ganhar navegação para `AlertsPage`, filtrada para mostrar só a categoria tocada.
- **`AlertsPage`** (`alerts_page.dart`) hoje sempre mostra as 5 seções (recomendações,
  sumidos, carência, prontos, estoque baixo, baixo desempenho) inteiras. Precisa de um
  jeito de abrir **só uma** seção quando vier do toque no dashboard — o dashboard só tem 3
  das 5 categorias (sumidos/carência/prontos), então só essas três precisam ser
  filtráveis por este fluxo.
- **Novo enum compartilhado**, ex. em `alerts_page.dart`:
  ```dart
  enum AlertCategoria { sumidos, carencia, prontosParaAbate }
  ```
  usado tanto pelo parâmetro novo de `AlertsPage` quanto pelo toque no dashboard — evita
  strings soltas e erro de digitação entre os dois arquivos.
- **`DashboardAlertCounts`** (`models.dart`) já tem os três campos com esses nomes exatos
  (`sumidos`/`carencia`/`prontosParaAbate`) — reuse, não crie um mapeamento novo.

## Contrato obrigatório

- **Reordenação**: em `_DashboardContent.build`, a seção "Alertas" (título + os 3
  `_AlertCountCard`s) vem **antes** de "Indicadores do rebanho" (título + grade de
  métricas + gráfico de raça, se houver). Nada muda dentro de cada seção, só a ordem
  relativa das duas.
- **`AlertsPage` ganha um parâmetro opcional**:
  ```dart
  const AlertsPage({
    super.key,
    required this.api,
    required this.onUnauthorized,
    this.focusCategoria,
  });
  final AlertCategoria? focusCategoria;
  ```
  Quando `focusCategoria != null`: renderize **só** a `_AlertSection` correspondente
  (nenhuma outra seção, incluindo Recomendações) — a tela abre já filtrada. Quando `null`
  (comportamento de hoje, usado pela entrada do Drawer): todas as seções, como sempre.
- **`_AlertCountCard` ganha `onTap`**, passado pelo `_DashboardContent`, que navega:
  ```dart
  Navigator.of(context).push(MaterialPageRoute(
    builder: (_) => AlertsPage(
      api: widget.api,
      onUnauthorized: widget.onUnauthorized,
      focusCategoria: AlertCategoria.sumidos, // ou .carencia / .prontosParaAbate
    ),
  ));
  ```
  (`DashboardResumoPage` precisa repassar `widget.api`/`widget.onUnauthorized` para dentro
  de `_DashboardContent`, que hoje só recebe `resumo` — adicione os dois campos que
  faltam.)

## Critério de aceite

1. No dashboard, a seção "Alertas" aparece visualmente antes de "Indicadores do rebanho"
   (teste comparando a posição vertical dos dois títulos, ex.
   `tester.getTopLeft(find.text('Alertas')).dy <
   tester.getTopLeft(find.text('Indicadores do rebanho')).dy`).
2. Tocar no card "Sumidos" do dashboard abre `AlertsPage` mostrando **só** a seção
   "🔴 Animais Sumidos" — nem Recomendações, nem Carência, nem as outras.
3. O mesmo para "Em carência" → só carência, e "Prontos para abate" → só prontos.
4. Abrir `AlertsPage` pelo Drawer (sem `focusCategoria`) continua mostrando as 5 seções
   completas, sem regressão.
5. Goldens de `dashboard_resumo_page` e `alerts_page` regenerados nos três temas.
6. `flutter analyze` limpo.

## Proibições

- ❌ Não filtre as duas categorias que o dashboard não mostra (estoque baixo, baixo
  desempenho) — elas não têm card no dashboard, `focusCategoria` só precisa cobrir as 3
  que têm.
- ❌ Não remova a navegação "todas as seções" pelo Drawer — `focusCategoria` é aditivo,
  opcional, nunca o único jeito de abrir a tela.
- ❌ Não mude a lógica de carregamento (`_load`, `getOperationalAlerts`,
  `getRecomendacoes`) — só o que é renderizado a partir do estado já carregado.
- ❌ Não toque `backend_api/` — nenhum dado novo é necessário, é reorganização de UI sobre
  dados que já chegam.

## Como verificar antes de abrir o PR

```bash
cd mobile
flutter analyze
flutter test
CAPTURE_GOLDENS=1 flutter test --update-goldens
```

## Entrega

PR para `main`, pronto para revisão.
