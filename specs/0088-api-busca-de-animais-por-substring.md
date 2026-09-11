# Spec 0088 — API: busca de animais por substring de ID/brinco

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** meio dia
- **Branch:** `feat/api-busca-de-animais`
- **Altere:** `backend_api/main.py`, `repositories/animais.py`, `tests/test_backend_api.py`
- **Pré-requisito:** nenhum

---

## Objetivo

Achado na auditoria de design (`DESIGN-IS-2026-09-10/03-verdict.md`, item #2): a caixa de
busca do mobile ("Buscar por ID ou brinco", `animals_page.dart:473-486`) filtra **só os
animais já carregados na tela** (`_animals`, no máximo `_pageSize=50` por página) — nunca
consulta o servidor. Numa fazenda com mais de 50 animais ativos, procurar um animal que não
está na primeira página não encontra nada, sem nenhum aviso de que a busca é parcial.

Esta spec resolve o lado servidor: um parâmetro de busca substring em `GET /animais`. A
[0089](0089-mobile-usar-busca-do-servidor.md) troca o filtro local do mobile por este.

## Contexto que você precisa

- **`repositories/animais.py::get_all_animals()`** (linha ~87) já filtra por `status`/
  `lote_id`/`breed` via `WHERE` — SQL parametrizado, nada de string interpolada. Adicione um
  quarto filtro opcional `id_contains: Optional[str] = None`, mesmo padrão:
  `AND a.id LIKE ?` com `args.append(f"%{id_contains}%")`. **Não precisa de índice novo** —
  a tabela já é pequena o bastante para `LIKE` sem índice dedicado (mesma escala que os
  filtros existentes já assumem).
- **`backend_api/main.py::list_animais`** (linha ~272) já carrega `get_all_animals(...)`
  inteiro na memória e só então pagina com slice Python (`all_animals[skip:skip+limit]`) —
  ou seja, a "paginação" de hoje já opera sobre uma lista filtrada em memória. Adicionar um
  novo parâmetro de query `q: Optional[str] = None` (nome curto, mesmo padrão REST comum) e
  passá-lo como `id_contains=q` para `get_all_animals` é uma mudança de poucas linhas — o
  slice de paginação continua igual, só que sobre a lista já filtrada por `q`.
- **"ID ou brinco" é a mesma coisa** — `backend_api/schemas.py:52` já documenta que
  `animals` não tem coluna `tag` separada, "o brinco já É o `id`". Não precisa buscar em
  duas colunas.
- Busca **case-insensitive** (brinco pode ser digitado com letras minúsculas mesmo se
  cadastrado maiúsculo, ou vice-versa) — `LIKE` no SQLite já é case-insensitive para ASCII
  por padrão; confirme que continua assim no Postgres de produção (usar `ILIKE` seria o
  equivalente lá, mas `repositories/` já abstrai o dialeto — confira como outros filtros de
  texto do projeto tratam isso, ex. `services/`, antes de decidir se precisa de tratamento
  condicional por dialeto).

## Contrato obrigatório

- `GET /animais?q=<substring>` — filtra por substring do `id`, case-insensitive, combinável
  com `status`/`skip`/`limit` já existentes (ex.: buscar só entre os `ativo`, paginado).
- `q` ausente ou vazio → comportamento idêntico ao de hoje (sem filtro).
- `q` sem nenhum animal correspondente → lista vazia, `200 OK` (não é erro).

## Critério de aceite

1. `GET /animais?q=BR000` retorna só animais cujo `id` contém `BR000` (substring, não
   prefixo — "contém" em qualquer posição).
2. Busca é case-insensitive: `q=br000` e `q=BR000` retornam o mesmo resultado.
3. `q` combinado com `status=ativo` e paginação (`skip`/`limit`) continua funcionando —
   filtros se compõem, não se substituem.
4. Sem `q`, resposta idêntica à de antes da mudança (nenhuma regressão no comportamento
   default).

## Proibições

- ❌ Não troque `LIKE`/parametrização por concatenação de string — SQL injection.
- ❌ Não adicione paginação nova nem mude o formato de resposta — é o mesmo endpoint, só
  com um filtro a mais.
- ❌ Não crie endpoint novo (`/animais/buscar` etc.) — é um parâmetro a mais no que já
  existe, mesmo padrão de `status`/`lote_id`/`breed`.

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t . -v
python -m compileall backend_api repositories tests
```

## Entrega

PR para `main`, pronto para revisão.
