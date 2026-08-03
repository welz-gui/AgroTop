# Spec 0019 — Rateio de custo de lote entre animais (função pura)

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 1 dia
- **Branch:** `feat/rateio-custo-lote`
- **Crie:** `services/rateio.py` e `tests/test_rateio.py` — **arquivos novos**

---

## Regra de ouro desta spec

Você cria **arquivos novos**. **Não altere nenhum arquivo existente.** Seu produto é uma
função pura, testada, com contrato fixo — o mantenedor liga à interface e ao banco depois
(ROADMAP R31).

## Objetivo

Custo de trato, medicamento aplicado no lote inteiro e frete chegam como **um valor para
N animais**. Hoje não há regra de como dividir, então esse custo simplesmente não entra no
custo individual — e o custo por arroba de cada animal fica **subestimado**.

Dividir igualmente é errado: um bezerro de 200 kg não come o mesmo que um boi de 450 kg.

## Contrato obrigatório

```python
def ratear(valor_total: float, animais: list[dict], criterio: str) -> list[dict]:
    """Divide um custo de lote entre os animais.

    `animais`: [{"id": str, "peso": float, "dias_no_lote": int}, ...]
    `criterio`: "igual" | "peso" | "peso_dia"

    Retorna [{"animal_id": str, "valor": float}, ...] cuja soma é EXATAMENTE
    `valor_total` — ver a regra de arredondamento abaixo.
    """
```

**Assine exatamente assim.**

## O detalhe que decide a correção: o centavo perdido

Rateio com arredondamento **não fecha**. R$ 100,00 entre 3 animais dá 33,33 × 3 = 99,99, e
some um centavo. Se isso acontecer, o custo total do lote deixa de bater com a soma dos
animais — e o relatório financeiro passa a se contradizer.

**Regra:** a soma dos valores devolvidos tem de ser exatamente `valor_total`, com 2 casas.
A diferença de arredondamento vai para o **maior** quinhão. Documente isso no docstring.

## Critérios

| `criterio` | Divide proporcionalmente a |
|---|---|
| `igual` | nada — mesmo valor para todos |
| `peso` | `peso` de cada animal |
| `peso_dia` | `peso × dias_no_lote` — o mais justo quando entram e saem em datas diferentes |

## Critério de aceite

1. **A soma sempre fecha**, com 2 casas, nos três critérios. Teste com R$ 100,00 entre 3
   animais — é o caso que expõe o centavo.
2. `peso_dia` cobra menos de um animal que ficou metade do período.
3. Lista vazia devolve lista vazia sem estourar.
4. Peso zero ou `dias_no_lote` zero não causa divisão por zero.
5. Valor negativo (estorno) é rateado com o mesmo critério, sem inverter sinal.

## Proibições

- ❌ Não toque em `app.py`, `database.py`, `repositories/`, `ui/`, nem em módulo existente
  de `services/`.
- ❌ **Não consulte banco.** Todos os dados entram por parâmetro — é o que torna a função
  testável sem fixture e reaproveitável na API e no mobile depois.
- ❌ Não crie tabela nem migration (R4: schema é do mantenedor).
- ❌ Não integre à interface.
- ❌ Não adicione dependência ao `requirements.txt` da raiz sem justificar no PR.
- ❌ Não invente critério novo além dos três. Se achar que falta um, **anote no PR**.

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t .
git diff --stat origin/main
```

O `-t .` não é opcional (R16) e o `AGROTOP_FORCE_SQLITE=1` é a segunda trava — sem os dois,
os testes podem conectar no banco de produção. No diff, só os dois arquivos novos.

## Entrega

PR para `main`, pronto para revisão. No corpo, mostre o teste do centavo: R$ 100,00 entre 3 animais, com a soma fechando.
