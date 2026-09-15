# Spec 0106 — Web: ficha do animal prioriza manejo, preserva histórico completo

- **Tipo:** implementação · **Risco:** médio · **Esforço:** 1-2 dias
- **Branch:** `feat/web-ficha-manejo-e-historico`
- **Altere:** `app.py::page_animal`, `app.py::_render_tab_peso`, prova de UI
- **Pré-requisito:** [spec 0095](0095-web-rebanho-selecao-coerente.md) (garante que o ID que
  chega à ficha é sempre o do animal realmente selecionado — pré-requisito técnico real desta
  spec; o "painel contextual" mais amplo do RD08 da proposta original **não** é pré-requisito,
  ver nota abaixo)

---

## Objetivo

RD09 da proposta de redesign (`DESIGN-IS-2026-09-10/proposta-specs-redesign-para-revisao-claude.md`)
e imagem 3 (`DESIGN-IS-2026-09-10/propostas-web/03-ficha-web-escuro.png`). A ficha
(`app.py::page_animal`, `app.py:2146-2247`) abre com 6 métricas neutras (Raça/Categoria/Peso/
Ganho/@/GMD) e só mostra a ação "Abrir no Campo" depois das 7 abas — a operação mais frequente
perde prioridade para a leitura de detalhes.

## Contexto que você precisa

- **Nota sobre pré-requisito**: a proposta original marca RD09 como dependente de RD08
  completo (seleção nativa do Streamlit + "painel contextual" reformulado no Rebanho). Isso
  **não aconteceu ainda** — só o bug de identidade foi corrigido (spec 0095/PR #414,
  confirmado em `app.py:1763`: `ids_filtrados = df["ID"].tolist()`). Mas o único motivo real
  para RD09 depender de RD08 era garantir que o ID chegando à ficha é estável e correto — isso
  já está garantido. O "painel contextual" do Rebanho (RD08 completo) é uma melhoria visual
  separada, não bloqueia esta spec.
- **Estrutura atual confirmada** (`app.py:2146-2247`):
  - Título + badge de status (`app.py:2166-2167`).
  - 6 métricas em `st.columns(6)`: Raça, Categoria, Peso Atual, Ganho, @ Atuais, GMD recente
    (`app.py:2169-2184`) — nenhuma é o peso-alvo (`target_weight`, existe no cadastro,
    `app.py:4698`, usado em outras telas como "Prontos para Abate" mas **nunca mostrado na
    ficha nem no gráfico de curva de peso**).
  - Editor de idade em `st.expander` (`app.py:2195-2203`) — mantenha como está, não é foco
    desta spec.
  - Aviso de carência (`app.py:2205-2207`) — já aparece antes das abas, correto.
  - `_consistencia_regulatoria` (`app.py:2210`) — mantenha.
  - 7 abas (`app.py:2212-2235`): Curva de Peso, Sanidade, Movimentações, Financeiro, Foto,
    Identificadores, Linha do Tempo.
  - Ações rápidas **depois** de tudo (`app.py:2238-2247`): "Abrir no Campo" (já seta
    `campo_id` e navega, `app.py:2240-2241` — **reuse exatamente este mecanismo, não crie
    um novo**), Dashboard, Rebanho.
- **`_render_tab_peso`** (`app.py:2056-2077`): gráfico de tendência + pesagens, sem nenhuma
  linha/marcador de meta (`target_weight`). Adicionar a meta como referência visual no mesmo
  gráfico (ex. `fig.add_hline`) é a forma mais direta de cumprir "curva de peso com contexto".
- **Raça/Categoria já são metadados de baixo destaque hoje** (colunas simples em
  `st.columns(6)`, mesmo peso visual que Peso/GMD) — a proposta pede que virem metadados
  visuais secundários, sem competir com peso/evolução.

## Contrato obrigatório

1. **Cabeçalho**: identidade do animal + badge de status continuam no topo. Adicione ação
   principal "Abrir no Campo" **no cabeçalho** (reusa `app.py:2240-2241` — não duplique lógica,
   mova/replique o botão), mantendo o bloco original no rodapé ou removendo-o de lá desde que
   a ação continue acessível em algum lugar óbvio — decida, mas não deixe sem ação nenhuma
   até rolar a página inteira.
2. **Resumo compacto** logo abaixo do cabeçalho: Peso atual, GMD recente e meta (`target_weight`,
   se presente — trate ausência como "Sem meta definida", nunca mostre zero). Raça/Categoria/
   Origem viram metadados visuais secundários (ex. `st.caption`, fonte menor) — não somem, só
   perdem destaque.
3. Carência e avisos regulatórios continuam visíveis antes das abas, sem mudança de posição
   relativa ao resumo.
4. **Curva de peso** (`_render_tab_peso`) ganha a linha/marcador de meta quando
   `target_weight` existir, na mesma unidade do eixo Y (kg) — não converta para @.
5. Todas as 7 abas continuam presentes, na mesma ordem, sem nova aba "Resumo" que duplique o
   conteúdo das outras.
6. "Voltar" (`app.py:2152`) continua restaurando a lista do Rebanho — confirme que o filtro/
   busca anteriores sobrevivem (comportamento existente, sem regressão).

## Critério de aceite

1. Animal sem `target_weight`, sem pesagens, com ganho zero válido, em carência ativa, sem
   carência e com falha ao carregar têm apresentação visualmente distinta (nenhum desses
   estados usa o mesmo texto genérico).
2. Nenhuma falha de consulta de sanidade aparece como confirmação verde (herda o cuidado já
   existente em `_consistencia_regulatoria`, sem regressão).
3. "Abrir no Campo" a partir do cabeçalho e "Voltar" não trocam o animal em nenhum momento —
   mesmo `aid` do início ao fim do fluxo.
4. As 7 abas continuam acessíveis em janela desktop (1366×768/1440×900) e estreita (sem
   nenhuma sumir por espaço).
5. Meta de peso aparece na curva quando existe, some sem quebrar o gráfico quando não existe.
6. Fluxo completo Rebanho → Ficha → "Abrir no Campo" → Voltar → Ficha continua no mesmo animal
   (`aid` idêntico do início ao fim).

## Proibições

- ❌ Não crie aba "Resumo" nova duplicando as 7 existentes.
- ❌ Não mexa no editor de idade (`app.py:2195-2203`) nem em `_consistencia_regulatoria`.
- ❌ Não converta a meta/curva para arrobas — peso vivo é sempre kg nesta tela.
- ❌ Não implemente "Registrar pesagem" direto na ficha nesta spec — a proposta permite manter
  "Abrir no Campo" se a pesagem direta não estiver implementada de verdade; não finja que
  existe com um botão sem formulário real por trás.
- ❌ Não toque `page_rebanho` além do necessário para navegação — o "painel contextual" do
  RD08 completo é uma spec separada, não esta.

## Como verificar antes de abrir o PR

```bash
$env:AGROTOP_FORCE_SQLITE = "1"
python -m unittest discover -s tests -t .
streamlit run app.py
```

## Entrega

PR para `main`, pronto para revisão. Prova do fluxo Rebanho → Ficha → Abrir no Campo → Voltar;
capturas dos estados principais (com/sem meta, com/sem carência, falha) nos temas claro e
escuro.
