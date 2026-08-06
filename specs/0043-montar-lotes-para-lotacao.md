# Spec 0043 — Montar dados de lote/piquete para `services/lotacao.py`

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 1 dia
- **Branch:** `feat/montar-lotes-lotacao`
- **Crie:** `services/lotacao_adaptador.py` e `tests/test_lotacao_adaptador.py` —
  **arquivos novos**

---

## Regra de ouro desta spec

Você cria **um arquivo novo**. **Não altere `services/lotacao.py`** — acabou de sair de
um retrabalho (spec 0028 → PR #94, defeito de CRS corrigido e verificado) e está correto.

## ⚠️ Esta spec NÃO cobre `sobrepostos()` — leia antes de reivindicar

`services/lotacao.py` tem quatro funções públicas: `lotacao`, `capacidade`,
`avaliar_lotacao` (as três desta spec) e `sobrepostos` (**fora**, de propósito).
`sobrepostos()` compara polígonos de piquetes — e `lotes` **não tem coluna de
polígono** (só `properties` tem, desde a spec 0032/PR #87). Ligar `sobrepostos()`
depende de uma migration que ainda não existe; não é trabalho de adaptador, é trabalho
de schema, e está registrado à parte no ROADMAP. Não tente contornar isso inventando um
formato de polígono alternativo.

## Contexto

`lotacao(area_ha, animais)`, `capacidade(area_ha, ua_por_ha_alvo)` e `avaliar_lotacao(...)`
já existem, puras, testadas — e usam só `area_ha` (que `lotes.area_ha` já tem) e uma
lista de animais com peso. O que falta é reunir "os animais deste lote, com o peso de
cada um" — hoje espalhado entre `animals.lote_id` e o peso atual de cada animal.

## Objetivo

Uma função pura que agrupa uma lista de animais por lote e monta a entrada de
`lotacao()`/`avaliar_lotacao()` para cada um.

## Contrato obrigatório

```python
def por_lote(
    animais: list[dict],
    # {"id": str, "lote_id": str | None, "peso": float, "status": str}
    lotes: list[dict],
    # {"id": str, "area_ha": float}
) -> dict[str, dict]:
    """
    {lote_id: {"area_ha": float, "animais": [{"peso": float}, ...]}}

    Só animais com `status == "ativo"` entram — animal vendido/morto não ocupa lotação
    de verdade, mesmo que `lote_id` ainda aponte para lá por atraso de baixa.

    Lote sem nenhum animal ativo aparece no dict com `"animais": []` — não é omitido:
    um piquete vazio é informação (`lotacao(area_ha, [])` já devolve zero UA/ha
    corretamente, é o critério de aceite 5 da spec 0028).

    Animal com `lote_id=None` ou `lote_id` que não corresponde a nenhum lote da lista
    `lotes` não entra em nenhum grupo — não invente um lote "sem piquete".
    """
```

## Regras que decidem a correção

**A saída é por lote, pronta para aplicar `lotacao()` e `avaliar_lotacao()` em
sequência, um lote de cada vez** — não agregue os lotes entre si. Quem chama itera o
dict e chama `services.lotacao.lotacao(info["area_ha"], info["animais"])` por chave.

**Animal com `peso` ausente ou `<= 0` ainda entra no grupo do lote** — a decisão de
ignorá-lo ou não é de `services/lotacao.py` (que já soma pesos, e peso zero soma zero,
sem distorcer o cálculo de UA/ha). Filtrar aqui seria decidir algo que já é decidido lá.

## Critério de aceite

1. Três animais ativos no mesmo lote produzem um grupo com os três pesos.
2. Animal com `status != "ativo"` não aparece em nenhum grupo, mesmo com `lote_id`
   válido.
3. Lote da lista `lotes` sem nenhum animal ativo aparece no resultado com
   `"animais": []`.
4. Animal com `lote_id` que não corresponde a nenhum lote em `lotes` não aparece em
   nenhum grupo — e não quebra a função.
5. `por_lote([], [])` devolve `{}`.
6. O resultado, aplicado com `services.lotacao.avaliar_lotacao(info["area_ha"],
   info["animais"], ua_por_ha_alvo=1.0)` para um lote com animais reais, produz uma
   situação (`"ocioso"`/`"adequado"`/`"sobrecarregado"`) sem exceção.

## Proibições

- ❌ **Não implemente nada relacionado a `sobrepostos()` ou polígonos.** Fora do escopo
  — ver o aviso no topo desta spec.
- ❌ Não altere `services/lotacao.py`.
- ❌ Não consulte banco.
- ❌ Não toque em `database.py`, `repositories/`, `app.py`.

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t .
git diff --stat origin/main
```

## Entrega

PR para `main`. No corpo, 2 lotes fictícios (um com animais, um vazio) e o resultado de
`avaliar_lotacao()` aplicado sobre a saída de `por_lote()` para o lote com animais.
