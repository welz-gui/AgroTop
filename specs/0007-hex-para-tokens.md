# Spec 0007 — Substituir os hex literais de `app.py` pelos tokens de `ui/tema.py`

- **Tipo:** manutenção · **Risco:** médio · **Esforço:** 2–3 dias
- **Branch:** `feat/hex-para-tokens`
- **Altere:** `app.py` e `ui/tema.py` · **Crie:** `tests/test_cores.py`

---

## ⚠️ Esta spec é exceção à regra de ouro

As outras proíbem tocar arquivo existente. Esta **precisa** — é o objeto do trabalho.
Continua valendo: **não toque em `database.py`, `repositories/` nem `services/`.**

## Por que estava bloqueada até agora

São ~198 hex literais em `app.py`, e nunca houve como **provar** que a troca não mudou a
aparência. Verificar a olho, tela por tela, não é verificação. O `AppTest` (desde o PR #44)
prova que um widget existe — **não qual cor ele tem**.

A saída não é comparar imagens. É comparar **valor por valor**: se `#4ade80` vira
`cores["sucesso"]` e `cores["sucesso"] == "#4ade80"`, a aparência **não pode** ter mudado —
é identidade, não semelhança.

## O mapa já existe

A **spec 0024** entregou `tools/auditar_cores.py`. Rode primeiro:

```bash
python tools/auditar_cores.py
```

O resultado conhecido em 2026-08-03:

| | |
|---|---:|
| Com token exato | **20 hex · 182 ocorrências (92 %)** |
| Sem token | 7 hex · 16 ocorrências (8 %) |

## O que fazer

### 1. Os 20 com token exato — substituição mecânica

Troque cada hex pela chave correspondente. **Só onde a cor é decisão de estilo**: hex em
`plotly` que compõe escala contínua (`color_continuous_scale`) também conta, mas confira
caso a caso.

### 2. Os 7 sem token — crie token novo

**Decisão do mantenedor, já tomada:** hex sem correspondente **ganha token novo, nomeado
pelo significado, aproximado ao mais próximo existente.**

O relatório da 0024 diz de qual token cada um está perto. Use isso para escolher o nome —
`#facc15` a 9,6 de `atencao` provavelmente é `atencao_claro`, não uma cor nova conceitual.

**Nomeie pelo significado, nunca pela aparência** (ROADMAP R20). `azul_link` é aceitável;
`azul_bonito` não. E o token precisa existir nos **dois temas** — escuro e claro.

⚠️ O tema claro **não é o escuro invertido**. `sucesso` é `#4ade80` no escuro e `#15803d`
no claro. Para cada token novo, escolha o par com o mesmo cuidado: o valor do claro tem de
ter contraste suficiente sobre fundo claro.

### 3. `tests/test_cores.py` — a prova

```python
def test_nenhum_hex_literal_sobrou_em_app_py()
    # usa tools/auditar_cores.extrair_hex; permite apenas a lista de exceções abaixo

def test_todo_token_existe_nos_dois_temas()
def test_valores_dos_tokens_nao_mudaram()
    # congela os 20 valores originais: se alguém mexer, o teste acusa
```

O terceiro é o mais importante: ele é a **prova de que a aparência não mudou**. Cole os 20
valores como constantes no teste, tirados do relatório da 0024.

## Exceções permitidas

Nem todo `#` some, e forçar isso pioraria o código:

- **CSS embutido em `st.markdown`** com `unsafe_allow_html` — se a string vier de f-string
  interpolando `cores[...]`, ótimo; se for CSS estático grande, pode ficar, **mas registre
  a exceção na lista do teste**.
- `manifest.json` e ícones — não executam Python e já são exceção declarada na R20.

## Critério de aceite

1. `python tools/auditar_cores.py` mostra **`sem token: 0`** ao final.
2. `tests/test_cores.py` passa e a lista de exceções está **explícita e comentada** — cada
   exceção diz por que ficou.
3. Os 20 valores originais continuam idênticos: nenhum token foi "ajustado" no caminho.
4. `AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t .` verde.
5. **Prova visual:** rode o app e cole capturas de **três telas** — dashboard, ficha do
   animal e alertas — nos dois temas. Não substitui os testes, mas pega o que eles não veem.

## Proibições

- ❌ **Não "melhore" nenhuma cor.** Se `#f87171` estava feio, continua feio. Mudar aparência
  nesta spec torna impossível saber se a substituição foi correta.
- ❌ Não renomeie token existente — há 200+ referências.
- ❌ Não toque em `database.py`, `repositories/`, `services/`.
- ❌ Não altere o comportamento de `ui/tema.py`, só acrescente tokens.

## Como verificar antes de abrir o PR

```bash
python tools/auditar_cores.py
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t .
git diff --stat origin/main
```

## Entrega

PR para `main`. No corpo: o relatório do `auditar_cores` **antes e depois**, a lista dos
tokens novos com o par escuro/claro de cada um, e as três capturas nos dois temas.
