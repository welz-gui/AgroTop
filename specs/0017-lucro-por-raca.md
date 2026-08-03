# Spec 0017 — Lucro por raça e cruzamento (função pura)

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 1 dia
- **Branch:** `feat/lucro-por-raca`
- **Crie:** `services/rentabilidade.py` e `tests/test_rentabilidade.py` — **arquivos novos**

---

## Regra de ouro desta spec

Você cria **arquivos novos**. **Não altere nenhum arquivo existente.**

## Objetivo

O sistema já sabe qual **fornecedor** rende mais (`get_fornecedor_ranking`). Não sabe qual
**raça** rende — e essa é a pergunta que decide a próxima compra.

A resposta muda conforme o que se mede: raça com maior lucro por cabeça pode ser a pior por
arroba produzida, e a que mais engorda pode ser a que mais custa. Esta função devolve as
três leituras para o pecuarista comparar, em vez de eleger uma.

## Contrato obrigatório

```python
def ranking_por_raca(ciclos: list[dict]) -> list[dict]:
    """Rentabilidade por raça, a partir de ciclos ENCERRADOS.

    `ciclos`: um item por animal vendido ou abatido —
        {
          "raca": str,
          "peso_entrada": float,   # kg
          "peso_saida": float,     # kg
          "dias": int,             # entrada até saída
          "custo_total": float,    # compra + insumos alocados
          "receita": float,
        }

    Retorna uma linha por raça, ordenada por `lucro_por_cabeca` decrescente:
        [{
          "raca": str,
          "animais": int,
          "lucro_por_cabeca": float,
          "lucro_por_arroba_produzida": float,
          "gmd_medio": float,
          "margem": float,          # lucro / receita. PODE SER NEGATIVA:
                                    # raça que deu prejuízo tem margem < 0, e
                                    # travar em zero faria prejuízo parecer empate
        }, ...]
    """
```

**Assine exatamente assim.** Use `services.constantes.KG_PER_ARROBA` e
`services.zootecnia` para conversão e GMD — **não reimplemente** cálculo que já existe.
Importar de `services/` é permitido; alterar aquelas funções, não.

## Regras de cálculo

- **Arroba produzida** é `(peso_saida - peso_entrada)` convertido, **não** o peso de
  carcaça na venda. A pergunta é quanto a fazenda produziu, não quanto o animal pesa.
- **Ciclo sem desfecho não entra.** Animal ainda ativo não tem receita; incluí-lo com
  receita zero afunda a média da raça e a resposta fica errada.
- **Raça com um animal só aparece**, mas o consumidor da função precisa saber disso — é
  para isso que serve `animais`. Não esconda amostra pequena; sinalize-a.

## Critério de aceite

1. Duas raças com lucro por cabeça igual mas GMD diferente ficam com
   `lucro_por_arroba_produzida` diferente — é o caso que prova que as três leituras não são
   a mesma coisa com outro nome.
2. Lista vazia devolve lista vazia, sem estourar.
3. Ciclo com `dias` = 0 não causa divisão por zero.
4. `margem` com receita zero não estoura.

## Proibições

- ❌ Não toque em `app.py`, `database.py`, `repositories/`, `ui/`, nem em módulo existente
  de `services/`.
- ❌ Não consulte banco: os ciclos entram por parâmetro.
- ❌ Não crie tabela nem migration.
- ❌ Não integre à interface.
- ❌ **Não invente rateio de custo indireto.** Se `custo_total` não trouxer, não estime —
  a spec não define alocação de custo fixo, e chutar aqui produz número que parece
  autoridade e não é.

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t .
git diff --stat origin/main
```

## Entrega

PR para `main`. No corpo, mostre um exemplo em que **a raça mais lucrativa por cabeça não
é a mais lucrativa por arroba** — é o que justifica a função devolver três leituras.
