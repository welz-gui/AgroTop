# Spec 0041 — Calcular `dias_no_lote` para alimentar `services/rateio.py`

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** meio dia
- **Branch:** `feat/dias-no-lote-rateio`
- **Crie:** `services/rateio_adaptador.py` e `tests/test_rateio_adaptador.py` —
  **arquivos novos**

---

## Regra de ouro desta spec

Você cria **um arquivo novo**. **Não altere `services/rateio.py`** — ele já foi provado
por teste de propriedade (spec 0031: a soma sempre fecha) e está correto.

## Contexto

Esta é a menor lacuna dos services órfãos. `services/rateio.py::ratear(valor_total,
animais, criterio)` já aceita `animais` no formato exato que precisa quando `criterio`
é `"igual"` ou `"peso"` — só o critério `"peso_dia"` (peso × dias no lote) precisa de um
campo, `dias_no_lote`, que não existe pronto em `animals`.

## Objetivo

Uma função pura de uma linha de lógica: calcula `dias_no_lote` a partir da data de
entrada do animal no lote atual e de uma data de referência.

## Contrato obrigatório

```python
def com_dias_no_lote(
    animais: list[dict],
    # {"id": str, "peso": float, "entrada_no_lote": "AAAA-MM-DD" | None}
    referencia: str,   # "AAAA-MM-DD" — normalmente hoje, ou a data do rateio
) -> list[dict]:
    """Devolve os mesmos dicts, acrescidos de `dias_no_lote: int`.

    `entrada_no_lote` ausente ou posterior a `referencia` (dado inconsistente) produz
    `dias_no_lote=0` — não erro, não data negativa. Zero dias é uma resposta segura:
    o animal entra no rateio por peso puro, com peso igual a zero dias, e portanto
    quinhão zero pelo critério `peso_dia` — o que é discutível, mas previsível e sem
    exceção. Se preferir outra regra, **implemente a que quiser, mas justifique no PR**
    — a spec não trava esse detalhe, trava só "nunca estoura, nunca fica negativo".
    """
```

## Regras que decidem a correção

**`dias_no_lote` é `(referencia - entrada_no_lote).days`, nunca negativo.** `max(0, ...)`
— animal com entrada futura por erro de digitação não pode gerar quinhão negativo no
rateio.

**Não invente de onde vem `entrada_no_lote`.** Não é objeto desta spec decidir se isso é
`animals.last_lote_entry` ou algo derivado de `animal_movements` — a função recebe o
valor já resolvido, por parâmetro, exatamente como está no contrato.

## Critério de aceite

1. Animal com `entrada_no_lote` 10 dias antes da `referencia` recebe `dias_no_lote=10`.
2. Animal com `entrada_no_lote=None` recebe `dias_no_lote=0`.
3. Animal com `entrada_no_lote` posterior a `referencia` recebe `dias_no_lote=0`, não
   negativo.
4. Os demais campos do dict original (`id`, `peso`, e quaisquer outros que o item já
   tivesse) permanecem intactos na saída — a função só acrescenta, não filtra nem
   reordena.
5. O resultado, passado para `rateio.ratear(valor, resultado, "peso_dia")`, produz uma
   soma de quinhões que fecha com `valor` (é o "teste do centavo" da spec 0031,
   verificado ponta a ponta).

## Proibições

- ❌ Não altere `services/rateio.py`.
- ❌ Não busque `entrada_no_lote` de tabela nenhuma — vem por parâmetro.
- ❌ Não toque em `database.py`, `repositories/`, `app.py`.

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t .
git diff --stat origin/main
```

## Entrega

PR para `main`. No corpo, 3 animais fictícios com datas de entrada diferentes, a saída
de `com_dias_no_lote()`, e o resultado de `ratear()` com critério `"peso_dia"` sobre ela.
