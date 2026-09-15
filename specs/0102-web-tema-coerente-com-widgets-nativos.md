# Spec 0102 — Web: gráficos e CSS seguem o tema que o usuário já escolheu no Streamlit

- **Tipo:** implementação · **Risco:** médio · **Esforço:** 1 dia
- **Branch:** `feat/web-tema-coerente-widgets-nativos`
- **Altere:** `app.py` (injeção de CSS/tema, `plotly_layout` nos gráficos), `tests/test_tema.py`,
  prova de UI dedicada
- **Pré-requisito:** [spec 0100](0100-web-base-visual-componentes.md) (RD04) — evita duas
  rodadas tocando o mesmo bloco de CSS

---

## Objetivo

RD05 da proposta de redesign (`DESIGN-IS-2026-09-10/proposta-specs-redesign-para-revisao-claude.md`).
**Achado que muda o design original da proposta**: o Streamlit **já tem** um seletor de tema
nativo (menu ⋮ → Settings → Theme, claro/escuro/sistema), com preferência persistida pelo
próprio navegador do usuário — não é preciso criar seletor nem persistência nova, como a
proposta original presumia. O problema real é mais estreito: `cores()`, `css_variaveis()` e
`plotly_layout()` (`ui/tema.py`) aceitam um parâmetro `tema`, mas **nada no app hoje lê qual
tema o Streamlit nativo está usando** — o CSS injetado e os gráficos Plotly sempre usam o
padrão (`escuro`), então se o usuário trocar para claro pelo menu nativo, os widgets do
Streamlit mudam mas o CSS customizado e os gráficos continuam escuros.

## Contexto que você precisa

- **API real, confirmada nesta revisão**: `st.context.theme.type` retorna `'dark'`, `'light'`
  ou `None` (tema não resolvido ainda) — é a leitura, do lado do servidor, do tema que o
  Streamlit nativo do usuário está usando naquele momento. Confirmado via
  `help(st.context.theme)` na versão instalada (1.57.0): `type: Literal['dark', 'light'] |
  None`.
- **Risco real a verificar primeiro**: `st.context` (e o sub-atributo `.theme`) é uma API
  relativamente recente do Streamlit. O piso do `requirements.txt` é `>=1.37.0`, mas isso
  **não garante** que a API existia nessa versão exata, nem que a versão realmente implantada
  em produção (Cloud Run) a suporta. **Passo 1 obrigatório desta spec**: confirmar
  `st.context.theme` funcionando de verdade contra o app rodando (local ou staging) antes de
  escrever qualquer linha do resto — se a API não existir na versão implantada, pare e
  reporte, não crie um fallback especulativo sem essa confirmação.
- **`None` é um estado real, não erro**: no primeiro render de uma sessão, antes do navegador
  informar a preferência, `st.context.theme.type` pode ser `None`. Trate como o padrão atual
  (`escuro`, `TEMA_PADRAO` de `ui/tema.py`) — nunca quebre nem mostre tema errado nesse
  instante.
- **`unit_pref`** (`app.py`, usado no rádio kg/@ da sidebar) é o precedente de estado
  server-side já existente no app, mas **não é o padrão certo aqui** — `unit_pref` é uma
  escolha que o usuário faz DENTRO do app; tema é uma escolha que o usuário já fez FORA dele
  (no menu nativo do Streamlit). Não duplique a preferência em `session_state`; leia
  `st.context.theme.type` a cada render.

## Contrato obrigatório

1. **Função central** (`app.py`, perto de onde `c = cores()` já é chamado no topo do
   script): resolva o tema ativo uma vez por render —
   ```python
   tema_ativo = st.context.theme.type or TEMA_PADRAO  # None → padrão atual
   c = cores(tema_ativo)
   ```
   (import `TEMA_PADRAO` de `ui.tema` se ainda não importado).
2. **`css_variaveis()`**: passe `tema_ativo` em vez de deixar no padrão implícito.
3. **Todo `plotly_layout(...)` chamado no arquivo** (múltiplos call sites — liste-os com
   `grep -n "plotly_layout("` antes de começar) passa a receber `tema_ativo` explicitamente
   em vez de confiar no padrão da função.
4. **`st.dataframe`/tabelas nativas, calendário, tooltips**: não precisam de código novo —
   já seguem o tema nativo do Streamlit automaticamente, é só o CSS/Plotly customizados que
   precisavam da correção acima.

## Critério de aceite

1. **Verificação manual primeiro** (não é teste automatizado, é pré-requisito): abrir o app
   rodando, trocar o tema pelo menu nativo do Streamlit (⋮ → Settings → Theme), confirmar que
   `st.context.theme.type` reflete a escolha — colar prova (captura de tela ou log) no PR
   antes de prosseguir com o resto.
2. Gráfico Plotly (qualquer um, ex. dashboard) muda de `plotly_dark` para `plotly_white`
   quando o tema nativo muda de escuro para claro, sem precisar de F5/novo login.
3. CSS customizado (badges, cards, `.page-title`) usa as cores do tema correto — mesmo
   contraste WCAG já garantido pela spec 0091, agora nos dois temas, não só no escuro.
4. `st.context.theme.type is None` (sessão nova, antes do navegador informar) não quebra a
   página nem mostra uma combinação inconsistente de cores.
5. Teste automatizado usando `AppTest` com o tema mockado (se `AppTest` permitir simular
   `st.context.theme` — confirme a capacidade real da API de teste antes de prometer isto no
   PR; se não for possível simular via `AppTest`, documente a limitação e cubra só com a
   prova manual do item 1).

## Proibições

- ❌ Não crie seletor de tema customizado na interface — o Streamlit já tem um nativo.
- ❌ Não crie coluna de banco nem `session_state` para persistir tema — a persistência já é
  responsabilidade do navegador/Streamlit nativo.
- ❌ Não mude `.streamlit/config.toml` — ele define o tema **padrão** para quem nunca
  escolheu nada, continua sendo `escuro`, sem mudança.
- ❌ Não prossiga com o resto da spec se o passo 1 (verificação da API contra produção) não
  confirmar que `st.context.theme` funciona — pare e reporte em vez de supor.

## Como verificar antes de abrir o PR

```bash
$env:AGROTOP_FORCE_SQLITE = "1"
python -m unittest tests.test_tema
python -m unittest discover -s tests -t .
streamlit run app.py   # verificação manual do item 1, trocando o tema pelo menu nativo
```

## Entrega

PR para `main`, pronto para revisão. Cole a prova da verificação manual (item 1 do critério
de aceite) no corpo do PR — sem ela, não há como confiar que a API se comporta como
documentado em produção.
