# Spec 0095 — Web: seletor de animal do Rebanho respeita os filtros aplicados

- **Tipo:** correção de bug · **Risco:** baixo · **Esforço:** meio dia
- **Branch:** `fix/web-rebanho-selecao-coerente`
- **Altere:** `app.py::page_rebanho`, `tests/ui_rebanho_prova.py` (novo), `tests/test_ui.py`
  (registrar o novo arquivo em `PROVAS`)
- **Pré-requisito:** nenhum

---

## Objetivo

Achado da revisão da proposta de redesign (`DESIGN-IS-2026-09-10/proposta-specs-redesign-para-revisao-claude.md`,
item RD08), **confirmado por leitura direta do código** (`app.py:1701-1763`, também
registrado em `docs/redesign-web-contratos-e-decisoes.md` §6): a tabela do Rebanho é filtrada
por busca/raça/categoria/status/lote, mas o seletor "Animal para detalhar" logo abaixo lista
**todos** os animais do rebanho, sem aplicar nenhum desses filtros. Um usuário pode filtrar a
tabela a 3 animais e escolher, no seletor, um dos outros 200+ que não estão nem visíveis na
tela.

## Contexto que você precisa

- **`page_rebanho()`** (`app.py:1701`): `animals_all = db.get_all_animals(status=None)` é a
  fonte de tudo. `df` é construído a partir de `animals_all` e depois filtrado em cascata
  (busca, raça, categoria, status, lote) — linhas 1737-1746.
- **O seletor problemático** (linha 1759): `sel=st.selectbox("Animal para detalhar",[a["id"]
  for a in animals_all])` — usa `animals_all` diretamente, ignorando `df` (o resultado já
  filtrado).
- **`calculate_gmd_bulk`/`get_withdrawal_end_batch`** (linhas 1722-1723) já buscam em lote
  para todos os animais antes do loop — **preserve essa chamada em lote**, não crie consulta
  por linha para "consertar" a seleção.
- **Seleção nativa do Streamlit** (`st.dataframe(..., on_select="rerun",
  selection_mode="single-row")`) está disponível na versão instalada (confirmado em
  `docs/redesign-web-contratos-e-decisoes.md` §1 — Streamlit 1.57.0, piso do
  `requirements.txt` é 1.37.0, a API existe desde 1.35). **Esta spec não exige usar seleção
  nativa** — trocar o `selectbox` para usar `df["ID"]` (a lista já filtrada) em vez de
  `animals_all` já resolve o bug com risco mínimo. Se optar por seleção nativa da tabela em
  vez do `selectbox`, documente a decisão no PR e prove que cobre os mesmos critérios de
  aceite abaixo — não é obrigatório, é uma opção mais trabalhosa com o mesmo resultado.

## Contrato obrigatório

- O seletor "Animal para detalhar" lista **exatamente os IDs presentes em `df`** (a tabela
  já filtrada), na mesma ordem, nunca `animals_all` diretamente.
- Se `df` ficar vazio (filtro sem resultado), o seletor fica vazio/desabilitado — nunca cai
  de volta para `animals_all`.
- Trocar um filtro que remove o animal atualmente selecionado invalida a seleção (o
  Streamlit já faz isso automaticamente ao recriar o `selectbox` com uma lista menor — só
  não force um valor `index` que não exista mais na lista nova).
- "📂 Abrir Ficha" continua abrindo exatamente o `sel` escolhido — sem mudança de
  comportamento além de qual conjunto de IDs pode ser escolhido.

## Critério de aceite

1. Filtrar a tabela a um subconjunto pequeno (ex.: uma raça específica) → o seletor mostra
   só os IDs desse subconjunto, nunca um ID fora dele.
2. Filtro sem nenhum resultado → seletor vazio, "Abrir Ficha" não abre um animal aleatório.
3. Selecionar um animal, depois trocar o filtro de forma que ele some da lista → seleção não
   persiste apontando para um ID que não está mais nas opções.
4. `calculate_gmd_bulk`/`get_withdrawal_end_batch` continuam sendo chamadas em lote, uma vez
   por carregamento da página — não uma vez por linha (prova via contagem de chamadas, mesmo
   padrão de outras provas do projeto que travam consulta em lote).
5. Sem nenhum filtro aplicado, comportamento idêntico ao de hoje (todos os animais
   disponíveis no seletor).

## Proibições

- ❌ Não crie paginação nova na tabela — fora de escopo desta correção.
- ❌ Não troque a estratégia de consulta em lote por consultas individuais por linha.
- ❌ Não mude os filtros existentes (busca, raça, categoria, status, lote) — só a fonte de
  dados do seletor abaixo da tabela.
- ❌ Não migre a página para seleção nativa de linha do `st.dataframe` a menos que documente
  e prove equivalência — o `selectbox` corrigido já resolve o bug relatado.

## Como verificar antes de abrir o PR

```bash
$env:AGROTOP_FORCE_SQLITE = "1"
python -m unittest tests.ui_rebanho_prova -v
python -m unittest discover -s tests -t .
```

## Entrega

PR para `main`, pronto para revisão.
