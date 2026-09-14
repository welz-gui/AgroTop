# Spec 0094 — Mobile: busca e cache offline com escopo verdadeiro

- **Tipo:** correção de bug · **Risco:** médio · **Esforço:** 1 dia
- **Branch:** `fix/mobile-busca-cache-offline-coerente`
- **Altere:** `mobile/lib/screens/animals_page.dart`, `mobile/lib/shallow_cache.dart`, testes
  correspondentes (`animals_page_test.dart`, `shallow_cache_test.dart`, `offline_flow_test.dart`)
- **Pré-requisito:** nenhum

---

## Objetivo

Achado da revisão da proposta de redesign (`DESIGN-IS-2026-09-10/proposta-specs-redesign-para-revisao-claude.md`,
item RD01), **confirmado por leitura direta do código** antes de virar spec: a busca no
servidor (spec 0089) reusa o mesmo cache raso da listagem geral, sem distinguir uma coisa da
outra. Offline, isso mostra ao usuário um resultado de busca antigo como se fosse a lista
completa do rebanho — ou o inverso, a lista geral como se fosse o resultado da busca atual.

## Contexto que você precisa

- **`_load({required bool reset})`** (`animals_page.dart:156-228`) roda tanto para a
  listagem geral quanto para toda busca (`_onQueryChanged` sempre chama
  `_load(reset: true)`, com `q: query.isEmpty ? null : query`).
- **A gravação do cache não distingue os dois casos**: `if (reset && _shallowCache != null)
  await _shallowCache.saveAnimals(page);` roda de igual forma com `query` vazio ou não —
  uma busca por "BR01" sobrescreve o cache que era da lista geral.
- **A leitura do cache no fallback (dois blocos, `on ApiException` e `catch` genérico) também
  não olha para `query`** — em ambos, `_shallowCache.getAnimals()` retorna o que estiver lá,
  não importa se foi salvo por uma busca ou pela lista geral, e o resultado vira `_animals`
  sem nenhum filtro local aplicado (desde a 0089, a filtragem é 100% do servidor).
- **`ShallowCache`** (`shallow_cache.dart:20-65`) usa uma chave fixa só,
  `cache_animais_list`/`cache_animais_list_time` — não tem conceito de "para qual consulta
  este cache vale".
- **Reproduza o defeito antes de corrigir** (a proposta pede isso explicitamente): escreva um
  teste que (1) carrega a lista geral online, (2) busca por um texto online (troca o cache),
  (3) simula falha de rede, (4) confirma que o fallback mostra dados errados/sem filtro —
  então corrija, e o mesmo teste vira a prova da correção.

## Contrato obrigatório

1. **Cache da listagem geral é preservado à parte** — uma busca (mesmo vazia de resultado)
   nunca sobrescreve o cache da lista geral (`getAnimals()`/`saveAnimals()` continuam
   servindo só a lista geral, sem `q`).
2. **Offline durante uma busca**: filtre os dados gerais já salvos em cache pelo texto atual
   (mesma normalização de ID já usada — `id.toLowerCase().contains(query.toLowerCase())`,
   igual ao filtro local que existia antes da 0089) e mostre "Busca nos dados disponíveis
   neste aparelho" + horário do cache geral. Isto não é uma promessa de cache completo do
   rebanho — é filtrar o que já está salvo localmente.
3. **Sem correspondência offline**: "Nenhum resultado nos dados salvos" — nunca "Nenhum
   animal encontrado" (que implica busca completa no rebanho). Sem cache nenhum: mensagem de
   indisponibilidade + tentativa de reconexão, comportamento já existente para a lista geral
   sem busca.
4. **Preserve debounce (400ms) e paginação da 0089** — troca de consulta reinicia
   `skip`/`_animals`; uma resposta de consulta antiga não pode atualizar lista, cache ou
   `_hasMore` da consulta atual (o `_loadGeneration` da 0089 já cobre isso — não duplique o
   mecanismo, reuse).
5. **`mounted`/geração conferidos também na gravação do cache** — se a tela fechar entre a
   resposta HTTP e `saveAnimals()`, não grave (evite `setState` pós-dispose e escrita de
   cache de uma tela já fechada).
6. **Cache legado**: o formato salvo hoje (`AnimalSummary` serializado) não muda — só o
   *quando* grava. Não é preciso migração; o cache antigo (lista geral sem filtro) continua
   válido como está na primeira leitura depois do deploy.

## Critério de aceite

1. Teste que reproduz o defeito primeiro (busca online sobrescrevendo cache geral), depois
   prova a correção com a mesma sequência.
2. Fluxo completo: lista geral → busca "A" online → offline → busca "B" → mostra resultado
   filtrado dos dados salvos localmente, rotulado como busca local, nunca como resultado
   completo do servidor.
3. Limpar a busca offline volta a mostrar a lista geral cacheada (não a última busca).
4. Cache vazio (nunca carregado) vs. cache existente sem correspondência — mensagens
   diferentes, conforme item 3 do contrato.
5. Resposta de uma busca antiga chegando depois de uma mais nova não substitui o resultado
   já exibido (teste do `_loadGeneration` continua verde, sem regressão).
6. Falha ao gravar o cache (ex.: `SharedPreferences` indisponível) depois de uma resposta
   HTTP válida não faz o resultado novo sumir da tela — persistência é uma etapa separada da
   exibição.
7. `401` continua limpando sessão e chamando `onUnauthorized`, sem regressão.

## Proibições

- ❌ Não crie cache completo do rebanho nem sincronização em segundo plano — escopo é só
  corrigir a confusão entre cache de busca e cache geral.
- ❌ Não duplique o `_loadGeneration`/debounce da 0089 — são mecanismos independentes do
  cache, já corretos, reuse-os.
- ❌ Não apague a fila de operações pendentes (`OfflineQueue`) nem o cache de detalhe do
  animal (`saveAnimalDetail`/`getAnimalDetail`) — fora de escopo.
- ❌ Não mude o endpoint `GET /animais` nem `backend_api/` — o bug é 100% client-side.

## Como verificar antes de abrir o PR

```bash
cd mobile
flutter analyze
flutter test test/animals_page_test.dart test/shallow_cache_test.dart test/offline_flow_test.dart
flutter test
```

## Entrega

PR para `main`, pronto para revisão. Cole no corpo do PR o teste que reproduziu o defeito
antes da correção — a proposta original pede isso explicitamente como prova de que o bug era
real, não hipotético.
