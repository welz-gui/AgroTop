# Redesign web — contratos e decisões (RD00)

**Status:** resolvido em 2026-09-14, pelo Claude, a pedido do usuário (que confirmou aprovação
das três imagens-conceito em `DESIGN-IS-2026-09-10/propostas-web/`).
**Base:** `HEAD` do repositório em 2026-09-14, depois do merge de 0084-0093.
**Objetivo:** fixar, uma vez, as decisões técnicas que RD01–RD13
(`DESIGN-IS-2026-09-10/proposta-specs-redesign-para-revisao-claude.md`) precisam para não
reinventar contrato cada spec do seu jeito. Nenhuma mudança de produto neste documento.

---

## 1. Versão real do Streamlit

- **Instalada neste ambiente:** `1.57.0` (`python -c "import streamlit; print(streamlit.__version__)"`).
- **`requirements.txt`:** só fixa o piso, `streamlit>=1.37.0` — não há pin de versão exata.
- **CI:** não pina Streamlit explicitamente em nenhum workflow (`.github/workflows/*.yml` só
  referenciam `.streamlit/**` como filtro de path, não como versão) — herda o que o
  `requirements.txt` resolver no momento do `pip install`.
- **Decisão:** `st.dataframe(..., on_select=..., selection_mode=...)` (seleção nativa de linha,
  disponível desde o Streamlit 1.35) **é seguro de usar** — está bem acima do piso de
  `requirements.txt` e da versão instalada aqui. RD08 pode usar seleção nativa em vez do
  `selectbox` desacoplado que existe hoje.
- **Armadilha confirmada:** hoje `on_select`/`selection_mode` não são usados em lugar nenhum de
  `app.py` (`grep` vazio) — a API existe, só nunca foi adotada. Não presumir parâmetros de uma
  versão mais nova sem checar contra `1.57.0`/`1.37.0` antes de usar.

## 2. Tema — mecanismo suportado hoje

- **Não existe seletor de tema no web.** Confirmado (spec 0091, reconfirmado agora):
  `grep -n "session_state.theme"` não encontra nada em `app.py`. `TEMA_PADRAO = "escuro"` em
  `ui/tema.py` é o único tema que o web já usou.
- **Não existe coluna `theme` em nenhuma tabela.** `grep -rn "theme" supabase/migrations/*.sql`
  vazio. A cautela do RD00 original ("não presumir que `users.theme` exista") era correta.
- **Decisão para RD05:** a primeira entrega usa **persistência só de sessão**
  (`st.session_state`, mesmo padrão já usado para `unit_pref`) — troca de tema sobrevive à
  navegação entre páginas na mesma sessão, mas não entre dispositivos nem sobrevive a um
  logout/login novo. **Isto não cumpre** a "sincronização de preferência entre dispositivos"
  que o `DESIGN.md` menciona como aspiração — RD05 deve dizer isso explicitamente no PR, não
  apresentar sessão como equivalente a persistência real.
- **Se cross-device virar requisito depois:** é uma dependência separada e fechada (nova
  migration + coluna em `users` + leitura/escrita na sessão de login) — nunca embutida
  silenciosamente dentro de uma spec visual, conforme a proposta original já exigia.

## 3. Navegação — inventário real (para RD06)

**Fonte:** `app.py::_sidebar` (linha 741) e `_go(page, animal_id=None)` (linha 196).

- **Admin — 20 destinos**, lista plana, sem agrupamento: Dashboard, Modo Campo, Rebanho,
  Lotes/Pastagem, Desempenho, Financeiro, Estoque, Brincos, Movimentação, Propriedades,
  Regras, Assistente IA, Sincronização, Nutrição, Sanitário, Clima & Chuva, Alertas,
  Relatórios, Cadastrar Animal, Admin.
- **Operador — 4 destinos:** Modo Campo, Cadastrar Animal, Estoque, Brincos.
- Badges dinâmicos existentes: Estoque (`🔴{len(low_stk)}`), Alertas (`🔴{n_alerts}`,
  soma de sumidos+carência+prontos+baixo estoque+baixo desempenho).
- Cabeçalho já mostra nome real e perfil (`{user['name']}` / "Administrador"/"Operador").
- Navegação troca de página com `_go(key)` + `st.rerun()`; o botão ativo já é destacado
  (`type="primary" if active else "secondary"`).
- **Confirma o achado de RD06 sem ressalva:** os 20/4 destinos batem exatamente com a tabela
  da proposta original. Nenhum destino a mais ou a menos foi encontrado.

## 4. Fluxo "Abrir no Campo" (para RD09)

- **Confirmado: não existe abertura direta do formulário de pesagem para um animal
  específico.** O botão "📱 Abrir no Campo" (`app.py:2232`, dentro de `page_animal`) só faz
  `st.session_state.campo_id = aid; _go("campo")` — leva ao Modo Campo genérico, que
  reaproveita `campo_id` para pré-preencher o campo de ID, mas segue o fluxo normal de
  confirmação (não pula direto para o formulário de pesagem).
- **Decisão para RD09:** manter "Abrir no Campo" como está — **não** prometer um botão
  "Registrar pesagem" que abra o formulário de pesagem direto, a menos que essa mudança seja
  implementada e testada como parte da própria RD09 (não é reaproveitamento de algo que já
  existe, seria funcionalidade nova).

## 5. Fontes de dado confirmadas (para RD07 — dashboard)

Funções reais por trás de cada indicador citado na proposta, todas já em uso:

| Indicador | Fonte |
|---|---|
| Total de animais, peso médio, GMD médio, arrobas produzidas | `db.get_rebanho_stats()` |
| Alertas (sumidos/carência/prontos) | `db.get_alert_animals()` |
| Estoque abaixo do mínimo | `db.check_low_stock()` |
| Baixo desempenho | `db.get_low_performance()` |
| Distribuição por raça | já em `app.py::_dash_chart_por_raca` (web) — mesma fonte que a 0085 expôs pra API |

Nenhum indicador citado nas imagens-conceito ("variação percentual", "atividade recente",
"melhor lote") tem função correspondente hoje — **RD07 não deve incluir nenhum desses três**,
por decisão já registrada na proposta original (§ RD07, "Acabamento").

## 6. `page_rebanho` — achado confirmado (para RD08)

**Confirmado exatamente como a proposta descreveu** (`app.py:1701-1763`):

- A tabela exibida (`df`) é filtrada por busca + raça + categoria + status + lote.
- O seletor abaixo — `st.selectbox("Animal para detalhar", [a["id"] for a in animals_all])`
  (linha 1759) — usa **`animals_all`, sem nenhum filtro aplicado**. Um usuário pode filtrar a
  tabela a 3 animais e escolher um dos outros 200+ no seletor, sem qualquer aviso.
- `calculate_gmd_bulk`/`get_withdrawal_end_batch` já batcheiam por todos os animais antes do
  loop — preservar essa chamada em lote é obrigatório (RD08 já dizia isso; confirmado que a
  função e a chamada existem exatamente como citado).

## 7. `page_animal` — achado confirmado (para RD09)

**Confirmado exatamente como a proposta descreveu** (`app.py:2137-2225`):

- 6 métricas (`st.columns(6)`) logo no título — Raça, Categoria, Peso Atual, Ganho, @ Atuais,
  GMD recente.
- Aviso de carência vem **depois** das métricas, não antes.
- As 7 abas (Curva de Peso, Sanidade, Movimentações, Financeiro, Foto, Identificadores, Linha
  do Tempo) ocupam o meio da página.
- Os três botões de ação (Abrir no Campo, Dashboard, Rebanho) ficam **no fim da página**,
  depois de todas as abas — mesmo padrão exato que a spec 0092 já corrigiu no mobile.

## 8. `R12`/`views/` — confirmado

`ROADMAP.md:148` proíbe `pages/` nativo do Streamlit; `ROADMAP.md:151` documenta `views/` como
extração permitida quando necessária. Ambos reais, citados corretamente pela proposta
original. Nenhuma das specs RD04-RD09 precisa criar `views/` — cabem como funções dentro de
`app.py`, mesmo padrão de todas as páginas existentes.

## 9. Capturas "antes" (pendente, não bloqueia a fila)

A proposta original pedia capturar as três telas atuais antes da mudança, em ambiente de
teste, com dimensão/tema/perfil registrados. **Não foi feito neste documento** — exige rodar
o app com dados de demonstração e navegador, fora do escopo de uma verificação de código. Cada
spec (RD07/RD08/RD09) deve capturar sua própria tela "antes" como parte do próprio PR
(seção "Como verificar"), não como pré-requisito bloqueante de RD00.

## 10. O que isto libera

Com as decisões acima fixadas, RD04-RD09 podem ser escritas como specs fechadas, sem
depender de descoberta durante a implementação. Nenhuma pendência deste documento bloqueia
o início de RD01, RD08, RD10 ou RD11 (não dependiam de RD00 tecnicamente, só precisavam da
confirmação da ordem de trabalho).
