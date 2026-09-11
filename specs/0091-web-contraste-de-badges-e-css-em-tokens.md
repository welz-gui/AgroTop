# Spec 0091 — Web: contraste WCAG dos badges e CSS custom movido para tokens de tema

- **Tipo:** manutenção · **Risco:** baixo · **Esforço:** meio dia
- **Branch:** `fix/web-contraste-badges-tokens`
- **Altere:** `app.py` (bloco de CSS, linhas ~100-159), `tests/test_tema.py`
- **Pré-requisito:** nenhum

---

## Objetivo

Achado na auditoria de design (`DESIGN-IS-2026-09-10/03-verdict.md`, item #4, evidência
`app.py:99-163` e `ui/tema.py:25-111`): o bloco `<style>` injetado em `app.py` é escrito com
hex literal, sem nenhuma referência a `ui/tema.py` — apesar de o módulo já expor exatamente
o mecanismo para isso (`css_variaveis()`, docstring do próprio arquivo: "No CSS, referencie
por variável — assim a folha de estilo não muda com o tema"). Conferido por grep:
`app.py` importa `cores`/`plotly_layout`/`SERIES`/`ESCALA_RUIM_BOM`/`ESCALA_BOM_RUIM` de
`ui.tema`, mas **nunca** `css_variaveis`.

Isso não é só estilo de código: dois pares de cor de badge, calculados (contraste WCAG,
fórmula de luminância relativa padrão), ficam **abaixo** do alvo 4,5:1 que o próprio
`ui/tema.py` declara como meta (linha 12) — `.badge-green` (texto `#4ade80` sobre fundo
`#166534`) mede **4,09:1**, e `.badge-red` (texto `#f87171` sobre fundo `#7f1d1d`) mede
**3,62:1**. Texto pequeno (`.78rem`, bem abaixo do limiar de "texto grande" que reduziria a
meta para 3:1).

## Contexto que você precisa

- **`app.py` não tem seletor de tema** — `TEMA_PADRAO = "escuro"` em `ui/tema.py` é o único
  tema que o web usa (confirmado: nenhum `st.selectbox`/toggle de tema em `app.py`, distinto
  do mobile que tem os três — escuro/claro/sistema). Esta spec **não precisa** lidar com
  troca de tema em runtime no web — só precisa que os valores venham de `ESCURO` via
  variável CSS, em vez de hex copiado à mão.
- **A troca é 1:1 valor-por-valor**, mesmo método já usado pela spec 0007 (`hex → tokens de
  tema`, [PR #100](https://github.com/welz-gui/AgroTop/pull/100)) — não precisa reinventar
  a abordagem, só aplicá-la a este bloco específico que ficou de fora daquela spec (o bloco
  de CSS bruto, diferente das ~198 ocorrências de hex em chamadas Python que a 0007 cobriu).
- **Mapa exato** (todo hex do bloco atual, `app.py:101-159`, para o token de `ui/tema.py::ESCURO`
  de valor idêntico — **exceto as duas linhas marcadas `FIX`**, que trocam de token para
  corrigir o contraste):

  | Seletor / propriedade | Hex atual | Token novo |
  |---|---|---|
  | `stSidebar` `background` | `#0a1628` | `var(--fundo_alt)` |
  | `stMetric` `background` | `#1e293b` | `var(--superficie)` |
  | `stMetric` `border` | `#334155` | `var(--borda)` |
  | `.page-title` `color`/`border-left` | `#4ade80` | `var(--primaria)` |
  | `.card` `background` | `#1e293b` | `var(--superficie)` |
  | `.card` `border` | `#334155` | `var(--borda)` |
  | `.card-green` gradiente | `#14532d` → `#0f172a` | `var(--sucesso_fundo)` → `var(--fundo)` |
  | `.card-green` `border` | `#166534` | `var(--sucesso_escuro)` |
  | `.card-yellow` gradiente | `#422006` → `#0f172a` | `var(--atencao_fundo)` → `var(--fundo)` |
  | `.card-yellow` `border` | `#854d0e` | `var(--atencao_escuro)` |
  | `.card-red` gradiente | `#450a0a` → `#0f172a` | `var(--perigo_fundo)` → `var(--fundo)` |
  | `.card-red` `border` | `#7f1d1d` | `var(--perigo_escuro)` |
  | `.badge-green` `background` | `#166534` | **`var(--sucesso_fundo)`** ⚠️ FIX (era `sucesso_escuro`) |
  | `.badge-green` `color` | `#4ade80` | `var(--sucesso)` |
  | `.badge-yellow` `background` | `#713f12` | `var(--atencao_fundo_alt)` |
  | `.badge-yellow` `color` | `#fbbf24` | `var(--atencao)` |
  | `.badge-red` `background` | `#7f1d1d` | **`var(--perigo_fundo)`** ⚠️ FIX (era `perigo_escuro`) |
  | `.badge-red` `color` | `#f87171` | `var(--perigo)` |
  | `.badge-blue` `background` | `#1e3a5f` | `var(--info_fundo)` |
  | `.badge-blue` `color` | `#60a5fa` | `var(--info_texto)` |
  | `.badge-gray` `background` | `#1e293b` | `var(--superficie)` |
  | `.badge-gray` `color` | `#94a3b8` | `var(--texto_secundario)` |
  | `.hist-item` `background` | `#0f172a` | `var(--fundo)` |
  | `.hist-item` `border-left` | `#4ade80` | `var(--primaria)` |
  | `.keypad-display` `color` | `#4ade80` | `var(--primaria)` |
  | `.keypad-display` `background` | `#0f172a` | `var(--fundo)` |
  | `.keypad-display` `border` | `#334155` | `var(--borda)` |
  | `collapsedControl button` `background` | `#4ade80` | `var(--primaria)` |
  | `collapsedControl button` `color` | `#0f172a` | `var(--fundo)` |

  As duas linhas `⚠️ FIX` são a correção de contraste em si: `sucesso_fundo` (`#14532d`) no
  lugar de `sucesso_escuro` (`#166534`) como fundo do badge verde mede **5,23:1**;
  `perigo_fundo` (`#450a0a`) no lugar de `perigo_escuro` (`#7f1d1d`) como fundo do badge
  vermelho mede **5,84:1** — ambos os tokens **já existem** em `ui/tema.py`, não precisa
  criar cor nova.
- **Injeção**: adicione `css_variaveis` ao import de `ui.tema` (linha 84) e injete
  `st.markdown(css_variaveis(), unsafe_allow_html=True)` **antes** do bloco `st.markdown`
  existente (a ordem entre os dois `<style>` não importa para `var()`/`:root` resolverem,
  mas mantenha antes por clareza de leitura).

## Contrato obrigatório

- Todo hex literal do bloco `app.py:101-159` substituído por `var(--token)`, conforme a
  tabela acima — sem exceção, sem hex novo introduzido.
- Aparência idêntica à de hoje em todas as regras **exceto** `.badge-green`/`.badge-red`
  (onde o fundo fica um pouco mais escuro — mesma família de cor, mudança sutil).
- `css_variaveis()` injetado uma vez, antes do bloco de regras.

## Critério de aceite

1. **Novo teste em `tests/test_tema.py`**: função helper de contraste WCAG (luminância
   relativa padrão — pode reimplementar a fórmula, é ~10 linhas, sem dependência nova) e um
   teste que calcula o contraste de `cores()["sucesso"]` sobre `cores()["sucesso_fundo"]` e
   de `cores()["perigo"]` sobre `cores()["perigo_fundo"]`, ambos `>= 4.5`. Isso trava contra
   regressão futura se alguém mudar esses tokens sem checar contraste de novo.
2. Teste (no mesmo arquivo, ou em `tests/` equivalente) que lê o bloco de CSS de `app.py`
   (pode ser via `re.findall(r'#[0-9a-fA-F]{6}', bloco)`) e confirma que **nenhum hex
   literal sobra** nele — só `var(--...)`.
3. `AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t . -v` — suíte completa
   verde, nenhuma prova de UI (`ui_*_prova.py`) quebrada pela troca de CSS.

## Proibições

- ❌ Não mude nenhum outro valor além dos dois `⚠️ FIX` — o resto é transcrição literal, não
  redesign.
- ❌ Não adicione seletor de tema no web — fora de escopo, o web continua fixo em `escuro`.
- ❌ Não toque `ui/tema.py` — os tokens `sucesso_fundo`/`perigo_fundo` já existem, não
  precisa criar nada lá.
- ❌ Não mexa em `mobile/` — cores do mobile já vêm de `app_colors.dart`, gerado à parte,
  fora do escopo desta spec.

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t . -v
python -m compileall app.py ui tests
grep -oE '#[0-9a-fA-F]{6}' app.py | sed -n '100,160p'   # conferência manual rápida do bloco
```

## Entrega

PR para `main`, pronto para revisão. Cole no corpo do PR os dois valores de contraste
calculados pelo novo teste (badge-green e badge-red), confirmando `>= 4.5`.
