# Spec 0105 — Web: dashboard com prioridades e alertas acionáveis

- **Tipo:** implementação · **Risco:** médio · **Esforço:** 1-2 dias
- **Branch:** `feat/web-dashboard-hierarquia-e-acoes`
- **Altere:** `app.py::page_dashboard` e os helpers `_dash_kpis`/`_dash_alerts`/
  `_dash_chart_*`/`_dash_summary_table` (mesmo arquivo), `app.py::page_alertas` (só o
  suficiente para aceitar foco por categoria), provas de UI
- **Pré-requisito:** [spec 0103](0103-web-navegacao-agrupada-por-tarefa.md) (RD06, mesclada)

---

## Objetivo

RD07 da proposta de redesign (`DESIGN-IS-2026-09-10/proposta-specs-redesign-para-revisao-claude.md`)
e imagem 1 (`DESIGN-IS-2026-09-10/propostas-web/01-dashboard-web-escuro.png`). O dashboard
(`app.py::page_dashboard`, confirmado em `app.py:852-878`) já tem a composição correta em
grandes linhas (KPIs → alertas → gráficos → tabela → conformidade), mas os cards de alerta
(`_dash_alerts`, `app.py:905-925`) são só `st.markdown` decorativo — tocar neles não faz nada.

## Contexto que você precisa

- **Composição atual já confirmada correta na ordem geral**: `_dash_kpis` → `_dash_alerts` →
  gráficos → `_dash_summary_table` → `_dash_conformidade`/`_dash_completude`
  (`app.py:852-878`). **Não precisa reordenar nada** — o problema real é só a falta de
  interação nos alertas, não a hierarquia.
- **7 KPIs hoje** (`_dash_kpis`, `app.py:895-902`): Animais, Peso Médio, GMD Médio,
  produção (kg ou @ conforme unidade), Lotação, Machos, Fêmeas. A proposta sugere até 4
  principais (animais/peso médio/GMD/arrobas) com o resto secundário — decida você a
  composição final, mas **não pode remover nenhum dos 7**, só redistribuir peso visual (ex.:
  4 em `st.metric` grande, 3 em `st.caption`/linha compacta abaixo).
- **Os três cards de alerta não têm ação** (`_dash_alerts`, `app.py:905-925`): são só
  `st.markdown` com HTML, sem `st.button` nem `on_click`. Streamlit não permite `onclick` em
  HTML puro — precisa envolver em `st.button` de verdade (como já faz `page_alertas` em
  `app.py:4252` para "Ir para Campo").
- **Não existe filtro de categoria de alerta no Rebanho** — `page_rebanho` (`app.py:1703-1721`)
  filtra por Raça/Categoria/Status/Lote. "Carência" **já existe** como valor de `Status`
  (`app.py:1717`: `["Todos","ativo","vendido","morto","carencia"]`) — para o card de Carência,
  prefira levar a `page_rebanho` com esse filtro pré-selecionado (mais direto que abrir
  Alertas). "Sumidos" e "Prontos para Abate" **não são status armazenados**, são condições
  calculadas em `db.get_alert_animals()` — não existe filtro equivalente no Rebanho, então
  esses dois vão para `page_alertas` (RD07 permite explicitamente este fallback).
- **`page_alertas` já existe** (`app.py:4197-` em diante) com abas "Operacionais"/
  "Conformidade" e seções Sumidos/Carência/Prontos dentro da aba Operacional — mas não recebe
  nenhum parâmetro de foco hoje. Precisa de um mecanismo novo, pequeno, no mesmo espírito do
  que a spec 0097 já fez no mobile (`focusCategoria` em `AlertsPage`) — mas adaptado ao padrão
  já usado no web (`st.session_state.campo_id`/`st.session_state.animal_detail`): um
  `st.session_state.alertas_foco` (`"sumidos"`/`"prontos"`/`None`) que `page_alertas` lê para
  abrir direto na aba/seção certa e mostrar de forma visível "Filtrando: Sumidos [Limpar]".
- **Gráficos já usam `_layout`/`PLOTLY` e o tema ativo** (confirmado em `_dash_chart_*`,
  `app.py:928-985`) — nada a mudar aí além do que a spec 0102 (RD05, tema) já cobre
  separadamente.

## Contrato obrigatório

1. Cada um dos três cards de `_dash_alerts` vira um `st.button` real (ou botão sobreposto ao
   card visual) com ação:
   - Sumidos → `st.session_state.alertas_foco = "sumidos"`; `_go("alertas")`; `st.rerun()`.
   - Carência → `_go("rebanho")` com o filtro de Status pré-setado para `"carencia"` (via
     `st.session_state`, seguindo o padrão já usado por outros filtros persistidos no app —
     confirme o mecanismo certo olhando como outros filtros de página sobrevivem a
     `st.rerun()` antes de inventar um novo).
   - Prontos para Abate → mesmo mecanismo do Sumidos, com `"prontos"`.
2. `page_alertas` lê `st.session_state.alertas_foco`: se setado, abre a aba "Operacionais" já
   selecionada, rola/destaca a seção correspondente (ou reordena para o topo — sua escolha,
   desde que fique óbvio) e mostra um indicador visível do filtro ativo com botão "Ver todos os
   alertas" que limpa `alertas_foco` e mostra a página completa de novo (mesmo espírito da
   spec 0097 mobile — não precisa ser texto idêntico).
3. Card de zero alertas (`n_sum==n_car==n_pro==0`, hoje some tudo em `app.py:908`) continua
   sem aparecer — comportamento preservado, não é regressão.
4. KPIs continuam mostrando os 7 valores de sempre — só a apresentação (tamanho/agrupamento)
   pode mudar.

## Critério de aceite

1. Tocar em cada um dos três cards de alerta leva ao destino certo com o filtro já aplicado —
   teste de ida e volta (abre filtrado, "Limpar"/"Ver todos" volta ao estado completo).
2. Os 7 KPIs continuam presentes e com os mesmos valores da base (não são recalculados nem
   somados de forma diferente).
3. Nenhum alerta consegue levar a uma tela sem indicar visualmente que há um filtro ativo —
   proibido implementar um botão que abre a lista genérica sem contexto (violaria o contrato
   da proposta original).
4. `page_rebanho` com filtro de Carência pré-setado mostra só animais com `Status=carencia`,
   igual a selecionar manualmente esse filtro no seletor existente.
5. Sem alertas de nenhuma categoria, a seção `_dash_alerts` continua invisível (comportamento
   atual preservado).
6. Perfil operador: confirme que `page_alertas`/`page_rebanho` continuam acessíveis a ele se
   já eram (`OPERATOR_PAGES`, sem mudança de permissão nesta spec).

## Proibições

- ❌ Não reordene os blocos do dashboard — a ordem atual (KPIs → alertas → gráficos → tabela →
  conformidade) já está correta.
- ❌ Não invente percentuais de variação, "atividade recente" ou "melhor lote" sem fonte —
  proibido explicitamente pela proposta original.
- ❌ Não crie paginação nem tela nova — só interação nos elementos existentes.
- ❌ Não toque `ui/tema.py` nem crie CSS de tema novo — isso é escopo da spec 0102.
- ❌ Não remova nenhum dos 7 KPIs nem as seções de conformidade/completude.

## Como verificar antes de abrir o PR

```bash
$env:AGROTOP_FORCE_SQLITE = "1"
python -m unittest discover -s tests -t .
streamlit run app.py   # clicar nos três cards de alerta e confirmar o destino/filtro
```

## Entrega

PR para `main`, pronto para revisão. Capturas antes/depois em 1366×768 e 1440×900, mostrando
os três cliques de alerta funcionando (não só a aparência estática).
