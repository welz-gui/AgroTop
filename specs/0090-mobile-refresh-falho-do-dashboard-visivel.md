# Spec 0090 — Mobile: refresh falho do dashboard nunca fica silencioso

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** meio dia
- **Branch:** `feat/mobile-dashboard-refresh-visivel`
- **Altere:** `mobile/lib/screens/dashboard_resumo_page.dart`, teste correspondente
- **Pré-requisito:** nenhum

---

## Objetivo

Mesma família do bug corrigido em `mobile/lib/screens/animals_page.dart` (falha de rede
virando afirmação de segurança sem aviso — ver [PR #391](https://github.com/welz-gui/AgroTop/pull/391)):
achado na auditoria de design (`DESIGN-IS-2026-09-10/03-verdict.md`, item #1, evidência
`dashboard_resumo_page.dart:31-69`). Não é a mesma gravidade (não afirma um estado de
segurança incorreto), mas é a mesma falha de honestidade — uma falha real fica invisível.

## Contexto que você precisa

- **`_DashboardResumoPageState._load()`** (linha ~31) trata erro em duas variantes
  (`ApiException`/genérico) e, nas duas, faz `setState(() => _error = ...)`.
- **`build()`** (linha ~56) só renderiza `_error` quando `_resumo == null` (`resumo == null
  ? (_error == null ? loading : _LoadError(...)) : RefreshIndicator(...)`). Ou seja: a
  **primeira** carga, se falhar, mostra erro corretamente. Um **refresh** (pull-to-refresh,
  `RefreshIndicator.onRefresh: _load` na linha ~66) que falhe **depois** de já haver dados
  carregados só grava `_error` — que nunca é lido, porque `resumo` já não é `null`. O
  usuário vê os dados antigos continuarem na tela, sem indicação nenhuma de que a
  atualização falhou (pode estar olhando números desatualizados achando que são atuais).
- **Padrão já usado no mesmo app** para avisar sobre um resultado sem bloquear a tela:
  `ScaffoldMessenger.of(context).showSnackBar(...)`, usado em
  `animals_page.dart::_openMedication`/`_openWeighing` depois de uma ação. O `Scaffold` já
  é o widget raiz do `build()` desta página — `ScaffoldMessenger.of(context)` funciona sem
  mudança de estrutura.

## Contrato obrigatório

- Falha na carga **inicial** (`_resumo == null`): comportamento **inalterado** — tela cheia
  de erro com `_LoadError`/retry, como hoje.
- Falha num **refresh** (`_resumo != null` no momento do erro): mantenha os dados antigos
  visíveis (não apague `_resumo`) **e** mostre um `SnackBar` com a mensagem de erro — nunca
  falhe em silêncio.
- Mensagem do `SnackBar` reusa a mesma extraída do erro (`error.message` para
  `ApiException`, ou a mensagem genérica já usada hoje para outros erros) — não invente uma
  mensagem nova.

## Critério de aceite

1. Teste que dá `pull-to-refresh` (mesmo padrão de
   `dashboard_resumo_page_test.dart::'pull-to-refresh recarrega o resumo com novos dados'`)
   com a segunda chamada a `/dashboard/resumo` retornando erro (500 ou exceção de rede):
   confirma que os dados antigos continuam visíveis (o card com o total antigo ainda
   aparece) **e** que um `SnackBar` com a mensagem de erro aparece
   (`find.byType(SnackBar)`/`find.text(...)`).
2. Falha na carga inicial continua mostrando `_LoadError` em tela cheia, sem regressão
   (teste já existente cobrindo isso não pode quebrar).
3. `flutter analyze` limpo.

## Proibições

- ❌ Não mude o comportamento da carga inicial — só o caso "já tinha dados, refresh falhou".
- ❌ Não adicione um banner permanente nem mude a estrutura da tela — `SnackBar` é
  transitório e já é o padrão do app para esse tipo de aviso.
- ❌ Não toque `backend_api/` nem outras telas — escopo é só esta página.

## Como verificar antes de abrir o PR

```bash
cd mobile
flutter analyze
flutter test test/dashboard_resumo_page_test.dart
```

## Entrega

PR para `main`, pronto para revisão.
