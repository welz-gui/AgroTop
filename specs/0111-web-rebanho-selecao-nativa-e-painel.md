# Spec 0111 — Web: Rebanho com seleção nativa de linha e painel contextual

- **Tipo:** implementação · **Risco:** alto · **Esforço:** 2 dias
- **Branch:** `feat/web-rebanho-selecao-nativa-e-painel`
- **Altere:** `app.py::page_rebanho`, prova de UI dedicada (`AppTest` + verificação manual em
  navegador para o que `AppTest` não reproduzir)
- **Pré-requisito:** [spec 0095](0095-web-rebanho-selecao-coerente.md) (mesclada — a base de
  identidade estável que esta spec substitui pelo mecanismo nativo),
  [spec 0106](0106-web-ficha-manejo-e-historico.md) (mesclada — a ficha já lê `target_weight`
  como meta, reuse o mesmo conceito no painel)

---

## Objetivo

RD08 completo da proposta de redesign (`DESIGN-IS-2026-09-10/proposta-specs-redesign-para-revisao-claude.md`).
**Escopo que ficou pendente de propósito**: a spec 0095 já corrigiu o bug de identidade
(seletor usava `animals_all` em vez do `df` filtrado) e a spec 0106 já depende só dessa
correção, não do resto do RD08 — documentado explicitamente nas duas specs. Esta é a spec
"separada" que ambas previram: troca o mecanismo de seleção (`st.selectbox` +botão "Abrir
Ficha") por seleção nativa de linha do `st.dataframe`, com um painel contextual ao lado da
tabela.

## Contexto que você precisa

- **Estado atual confirmado** (`app.py::page_rebanho`, `app.py:1738-1826`): filtros (busca,
  raça, categoria, status, lote) já funcionam e já persistem entre reruns via
  `st.session_state.rebanho_status` (spec 0105) — **não mexa nesse mecanismo de filtro**, só
  no que vem depois da tabela. Hoje: `st.dataframe` sem seleção nativa
  (`app.py:1807-1810`), seguido de `st.selectbox("Animal para detalhar", ids_filtrados)` +
  botão "📂 Abrir Ficha" (`app.py:1813-1826`).
- **API nativa confirmada disponível** (pesquisa da spec 0102, mesma versão instalada,
  Streamlit 1.57.0): `st.dataframe(df, on_select=..., selection_mode="single-row")` retorna um
  evento de seleção com o(s) índice(s) de linha selecionado(s) **no DataFrame efetivamente
  passado ao widget** — resolva o ID a partir desse índice contra o `df` já filtrado
  (`app.py:1782` em diante), nunca contra `animals_all` nem contra uma posição visual
  assumida. Confirme o formato exato do evento retornado (`st.session_state[key].selection.rows`
  ou equivalente) lendo `help(st.dataframe)`/a documentação antes de escrever o código — não
  assuma a forma do objeto.
- **Risco real a verificar primeiro**: `AppTest` pode não reproduzir o evento de seleção de
  `st.dataframe` fielmente (a proposta original já avisa disso). **Passo 1 obrigatório**:
  confirme, escrevendo um teste mínimo, se `AppTest` consegue simular a seleção. Se não
  conseguir, documente a limitação no PR e cubra o mecanismo de seleção com prova manual em
  navegador (`streamlit run app.py`, captura de tela) em vez de fingir cobertura automatizada
  que não existe.
- **Meta de peso**: `target_weight` (usado na ficha desde a spec 0106) — mostre no painel
  quando presente, "Sem meta definida" quando não (mesmo padrão da spec 0106, não invente um
  formato novo).
- **`calculate_gmd_bulk`/`get_withdrawal_end_batch`** (`app.py:1768-1769`) já calculam em lote
  para toda a tabela — o painel contextual **reusa esses valores já calculados** para o animal
  selecionado, não faz uma consulta nova por seleção.
- **`_go("animal", sel)`** (`app.py:1825`) é o mecanismo existente para abrir a ficha — reuse,
  não crie um caminho novo de navegação.

## Contrato obrigatório

1. Troque `st.dataframe` simples por `st.dataframe(df, on_select="rerun",
   selection_mode="single-row", ...)` (ou equivalente confirmado no passo de pesquisa acima).
   Remova o `st.selectbox("Animal para detalhar", ...)` — a seleção agora vem da própria
   tabela.
2. **Painel contextual**, ao lado da tabela em tela larga (tabela ocupando a maior parte,
   painel a coluna complementar — ex. `st.columns([3, 1])` ou proporção similar), abaixo da
   tabela em janela estreita: cabeçalho com ID, raça/categoria e status; peso atual, GMD
   recente e meta (`target_weight`) quando presentes; contexto de lote e carência; botões
   "Abrir ficha" (reusa `_go("animal", id)`) e "Abrir no Campo" (mesmo mecanismo de
   `campo_id`/`_go("campo")` já usado na ficha e no dashboard).
3. **Sem seleção**: painel mostra orientação (ex. "Selecione um animal na tabela para ver os
   detalhes") — nunca seleciona nem mostra um animal aleatório.
4. **ID resolvido contra o `df` filtrado efetivamente renderizado**, nunca contra
   `animals_all` nem por posição assumida — mesmo cuidado que a spec 0095 já corrigiu, agora
   aplicado ao mecanismo nativo.
5. **Invalidação de seleção**: se o animal selecionado sair do filtro atual (troca de filtro)
   ou deixar de existir nos dados atualizados (rerun por qualquer motivo), o painel volta ao
   estado "sem seleção" com uma explicação — nunca mantém um ID de seleção que não está mais
   na tabela renderizada.
6. Sem resultados na tabela (filtro elimina tudo): oferece "Limpar filtros" — não deixa o
   painel numa seleção órfã.

## Critério de aceite

1. Fluxo completo: filtrar → selecionar A → ordenar a tabela pela coluna → abrir ficha ainda
   abre o animal A (ou exige nova seleção explícita se a ordenação invalidar a posição —
   documente qual dos dois comportamentos foi implementado e por quê).
2. Mudar um filtro que remove A da lista limpa o painel automaticamente.
3. Atualizar os dados (rerun) não troca A por outro animal só por causa da posição na tabela.
4. Limpar filtros mantém comportamento coerente (painel some se A não estava mais visível
   antes de limpar).
5. Nenhuma ação do painel ("Abrir ficha"/"Abrir no Campo") usa um animal diferente do
   destacado na tabela no momento do clique.
6. Busca, retorno à lista (a partir da ficha), tema e unidade (kg/@) continuam funcionando sem
   regressão.
7. `calculate_gmd_bulk`/`get_withdrawal_end_batch` continuam sendo a única fonte dos valores do
   painel — nenhuma consulta nova por linha/seleção (compare chamadas ao banco antes/depois).
8. Tabela mantém valores numéricos para ordenação (não perde a capacidade de ordenar por peso/
   GMD só porque ganhou formatação de exibição).

## Proibições

- ❌ Não introduza paginação nova só porque um mockup sugere — se a tabela precisar de
  paginação por outro motivo, isso é contrato de uma spec própria.
- ❌ Não crie consulta ao banco por linha/seleção — reuse os lotes já calculados.
- ❌ Não toque o mecanismo de filtros (`rebanho_status`, busca, raça, categoria, lote) além do
  necessário para a seleção — ele já funciona (specs 0095/0105).
- ❌ Não implemente pesagem direta no painel nesta spec — "Abrir no Campo" continua sendo a
  ação, a menos que um formulário de pesagem direta já exista de verdade (não existe hoje).
- ❌ Não finja cobertura de `AppTest` para o evento de seleção se ele não reproduzir de
  verdade — documente a limitação e use prova manual.

## Como verificar antes de abrir o PR

```bash
$env:AGROTOP_FORCE_SQLITE = "1"
python -m unittest discover -s tests -t .
streamlit run app.py   # prova manual do mecanismo de seleção, se AppTest não reproduzir
```

## Entrega

PR para `main`, pronto para revisão. Capturas com seleção, sem seleção, vazio e largura
estreita; comparação de chamadas em lote antes/depois (prova de que não há regressão de
consultas por linha); se `AppTest` não reproduzir o evento de seleção, inclua a prova manual
no lugar.
