# Spec 0101 — Mobile: dashboard mostra quando os dados ficaram desatualizados

- **Tipo:** manutenção · **Risco:** baixo · **Esforço:** meio dia
- **Branch:** `feat/mobile-dashboard-estado-desatualizado`
- **Altere:** `mobile/lib/screens/dashboard_resumo_page.dart`,
  `mobile/test/dashboard_resumo_page_test.dart`, goldens correspondentes
- **Pré-requisito:** nenhum

---

## Objetivo

RD02 da proposta de redesign (`DESIGN-IS-2026-09-10/proposta-specs-redesign-para-revisao-claude.md`)
— complemento explícito da [spec 0090](0090-mobile-refresh-falho-do-dashboard-visivel.md), que
resolveu o refresh falho mostrando um `SnackBar` transitório. O `SnackBar` some sozinho depois
de alguns segundos; se o usuário olhar a tela minutos depois, não há nenhum indício de que os
números na tela são de uma consulta antiga que falhou ao atualizar. **Isto não é falha da
0090** — ela proibia banner permanente por decisão explícita de escopo, e este é exatamente
o complemento que a própria spec previa.

## Contexto que você precisa

- **`_handleError`** (`dashboard_resumo_page.dart:58-66`) hoje só distingue "carga inicial
  falhou" (`_resumo == null` → tela cheia de erro) de "refresh falhou com dados já na tela"
  (`SnackBar`). Nada é lembrado depois que o `SnackBar` desaparece.
- **Formato de horário já usado no app**: `ShallowCache.CachedData.formattedTime`
  (`shallow_cache.dart`) faz exatamente `'$h:$m'` com `padLeft(2,'0')` — reuse o mesmo padrão
  (copie a lógica pequena ou extraia um helper comum, à sua escolha, mas não invente um
  formato de hora diferente do que o app já usa em `OfflineCacheBanner`).
- **`OfflineCacheBanner`** (`mobile/lib/screens/offline_cache_banner.dart`) já é o precedente
  visual de "aviso persistente com horário" usado no app — mesmo espírito, mas para um motivo
  diferente (cache offline vs. refresh falho online). Não precisa reusar o widget em si (os
  textos são diferentes), mas siga a mesma altura/estilo visual para consistência.

## Contrato obrigatório

1. **Novo estado**: `DateTime? _staleSince` — guarda o momento em que o refresh começou a
   falhar (não a hora do último sucesso; é "desde quando os dados podem estar errados").
   `String? _staleMessage` — a mensagem de erro do refresh falho.
2. **Ao falhar um refresh com dados já na tela** (`_resumo != null`): além do `SnackBar` já
   existente (mantenha-o — feedback imediato continua útil), grave `_staleSince ??=
   DateTime.now()` (só na primeira falha de uma sequência — não reinicie o relógio a cada
   nova tentativa falha) e `_staleMessage = message`.
3. **Banner persistente**, renderizado entre a `AppBar` e o conteúdo, visível sempre que
   `_staleSince != null`:
   ```
   "Não foi possível atualizar — última tentativa bem-sucedida antes de HH:MM"
   ```
   (o horário é de `_staleSince`, que é quando a falha começou — não confunda com hora dos
   dados do rebanho em si). Com botão/ação "Tentar novamente" chamando `_load`.
4. **O banner só desaparece após um refresh bem-sucedido** — em caso de sucesso, `_staleSince
   = null` e `_staleMessage = null` junto com a atualização normal de `_resumo`.
5. **Carga inicial continua sem mudança** — `_staleSince` só é setado quando já havia
   `_resumo` (isto é, é estritamente sobre refresh, nunca sobre a primeira carga).

## Critério de aceite

1. Carga inicial bem-sucedida → refresh falha → banner aparece com a hora certa.
2. Sucesso → falha → esperar mais que a duração do `SnackBar` (ex. `tester.pump(Duration(seconds:
   5))`) → banner continua visível (diferente do `SnackBar`, que já teria sumido).
3. Falhas repetidas em sequência não reiniciam `_staleSince` — a hora mostrada é da primeira
   falha da sequência, não da mais recente.
4. Retry bem-sucedido some com o banner.
5. Carga inicial falha → tela cheia de erro, sem o banner novo (comportamento da 0090
   preservado, sem regressão).
6. 401 durante qualquer refresh continua chamando `onUnauthorized` sem mudança.

## Proibições

- ❌ Não remova o `SnackBar` já existente — o banner é aditivo, não substituto.
- ❌ Não crie persistência entre sessões do app (SharedPreferences etc.) — o estado é só da
  tela atual, se o usuário sair e voltar, começa limpo.
- ❌ Não adicione polling nem atualização em segundo plano — fora de escopo, só o estado
  visual de uma falha já ocorrida.
- ❌ Não mude o comportamento de carga inicial.

## Como verificar antes de abrir o PR

```bash
cd mobile
flutter analyze
flutter test test/dashboard_resumo_page_test.dart
CAPTURE_GOLDENS=1 flutter test --update-goldens
```

## Entrega

PR para `main`, pronto para revisão.
