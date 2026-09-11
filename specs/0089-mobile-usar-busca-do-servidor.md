# Spec 0089 — Mobile: usar a busca do servidor em vez de filtrar só a página carregada

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** meio dia
- **Branch:** `feat/mobile-busca-de-animais-no-servidor`
- **Altere:** `mobile/lib/api_client.dart`, `mobile/lib/screens/animals_page.dart`, testes
  correspondentes
- **Pré-requisito:** [spec 0088](0088-api-busca-de-animais-por-substring.md) (API) — precisa
  estar mesclada e em produção antes desta

---

## Objetivo

Lado mobile do achado da auditoria (item #2 de `03-verdict.md`): hoje a busca
(`animals_page.dart:457-460`) filtra só `_animals`, a lista já carregada na tela (no máximo
`_pageSize=50` por página). Animal fora da primeira página nunca aparece na busca, sem
nenhum aviso disso — parece "não encontrado" quando na verdade é "não carregado ainda".

## Contexto que você precisa

- **`ApiClient.listAnimals()`** (`mobile/lib/api_client.dart:85-...`) já monta a query com
  `skip`/`limit`/`status` — adicione um parâmetro opcional `String? q`, incluído nos
  `queryParameters` só quando não nulo/vazio (mesmo padrão condicional que outros parâmetros
  opcionais do client já usam em outros métodos).
- **`_AnimalsPageState`** (`animals_page.dart:56-...`) tem `_query` (o texto digitado) e
  `_animals`/`_hasMore`/`_loading` (estado de paginação). Hoje a filtragem é local e
  síncrona (`build` recalcula a cada rebuild); precisa virar uma busca no servidor —
  assíncrona, com debounce (não disparar uma requisição a cada tecla digitada).
- **Debounce**: use `Timer` (já é `dart:async`, sem dependência nova) — cancele o timer
  anterior a cada `onChanged`, dispare a busca só depois de ~400ms sem digitar. Padrão comum
  em Flutter, não precisa de pacote.
- **Quando `_query` estiver vazio**, volte ao comportamento de hoje: lista paginada normal,
  sem filtro — não é "buscar por string vazia" no servidor, é "sem busca".
- **Estado de carregamento da busca** precisa de um indicador (a lista pode demorar um
  round-trip de rede) — reuse o padrão já existente de `_loading`/`CircularProgressIndicator`
  desta mesma tela, não invente um novo.

## Contrato obrigatório

- Texto na caixa de busca → após debounce, chama `widget.api.listAnimals(q: texto, status:
  'ativo')` (busca sempre entre os `status` já selecionados/padrão da tela) e substitui a
  lista exibida pelo resultado — não mais um `.where()` local sobre `_animals`.
- Texto vazio → volta à listagem paginada normal (sem `q`), preservando `_hasMore`/"Carregar
  mais" como hoje.
- **"Carregar mais" durante uma busca ativa** também deve repassar o mesmo `q` (senão a
  segunda página perde o filtro) — `skip` avança sobre o resultado filtrado, não sobre a
  lista total.

## Critério de aceite

1. Buscar um ID que exista, mas que não estivesse entre os primeiros 50 carregados,
   encontra o animal (teste com mock server retornando >50 animais, ID buscado fora da
   primeira página).
2. Limpar o campo de busca volta à listagem paginada normal.
3. Debounce confirmado: digitar rápido (`pumpAndSettle` não usado nesse trecho do teste,
   `tester.pump()` com durações curtas) não dispara uma requisição por tecla — só uma,
   depois da pausa.
4. "Carregar mais" com busca ativa preserva o filtro na página seguinte.
5. Golden/widget test da tela de lista não quebra com o campo de busca vazio (comportamento
   inicial idêntico ao de hoje).

## Proibições

- ❌ Não remova o `_pageSize`/paginação — a busca é mais uma dimensão do filtro, não troca a
  paginação por "carregar tudo de uma vez".
- ❌ Não adicione dependência de debounce (`easy_debounce` etc.) — `Timer` do `dart:async`
  já resolve.
- ❌ Não altere `backend_api/` — esta spec só consome o que a 0088 já expõe.

## Como verificar antes de abrir o PR

```bash
cd mobile
flutter analyze
flutter test
CAPTURE_GOLDENS=1 flutter test --update-goldens
```

## Entrega

PR para `main`, pronto para revisão. Confirme no corpo do PR que partiu da spec 0088 já
mesclada.
