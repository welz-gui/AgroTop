# Spec 0034 — Normalizar registros financeiros heterogêneos para `services/caixa.py`

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 1-2 dias
- **Branch:** `feat/normalizar-lancamentos`
- **Crie:** `services/lancamentos.py` e `tests/test_lancamentos.py` — **arquivos novos**

---

## Regra de ouro desta spec

Você cria **um arquivo novo**. **Não altere nenhum código de produção.** Se achar que o
resultado deveria vir de outra combinação de tabelas, **anote no PR — não implemente.**

## Contexto: o que já existe e por que não basta

`services/caixa.py` (`resultado_por_competencia`, `fluxo_de_caixa`, `em_aberto`) é função
pura, testada, e nunca foi chamada. Ela espera uma lista única de **lançamentos**, cada um
no formato:

```python
{"tipo": "receita" | "despesa", "valor": float, "categoria": str,
 "competencia": "AAAA-MM-DD" | None,   # a que mês o fato pertence
 "vencimento": "AAAA-MM-DD" | None,    # quando devia ser pago
 "pagamento": "AAAA-MM-DD" | None}     # quando foi pago de fato; None = em aberto
```

O problema é que o dinheiro do AgroTop está espalhado em quatro tabelas com formatos
diferentes — `sales` (venda, é receita), `fixed_costs` (é despesa), `animal_costs` (é
despesa), `insumo_transactions` do tipo `compra` (é despesa) — e nenhuma delas fala a
língua que `caixa.py` entende.

## Objetivo

Uma função pura que recebe as quatro listas cruas (já buscadas por quem chamar — nenhum
`SELECT` aqui) e devolve a lista única de lançamentos.

## Contrato obrigatório

```python
def normalizar(*, vendas: list[dict] = (), custos_fixos: list[dict] = (),
              custos_animal: list[dict] = (), compras_insumo: list[dict] = ()) -> list[dict]:
    """
    `vendas`: linhas de `sales` — usa `sale_date`, `total_value`.
        tipo="receita", categoria="venda", competencia=vencimento=pagamento=sale_date
        (venda é reconhecida na data da venda, sempre paga naquele instante no modelo
        atual — não há venda a prazo registrada separadamente).

    `custos_fixos`: linhas de `fixed_costs` — usa `cost_date`, `amount`, `category`.
        tipo="despesa", categoria=`category`, competencia=vencimento=pagamento=cost_date.

    `custos_animal`: linhas de `animal_costs` — usa `cost_date`, `amount`, `cost_type`.
        tipo="despesa", categoria=`cost_type`, competencia=vencimento=pagamento=cost_date.

    `compras_insumo`: linhas de `insumo_transactions` — só as de `type == "compra"`;
        as demais (`consumo`, `ajuste`, etc.) NÃO são lançamento financeiro e devem ser
        ignoradas. Usa `transaction_date`, `quantity` × custo unitário — mas
        `insumo_transactions` não guarda o custo: ver "O que fazer quando falta o
        preço" abaixo.

    Retorna a lista única, na forma que `services/caixa.py` espera. Ordem não importa —
    quem consome já agrega por competência/período.
    """
```

## O que fazer quando falta o preço

`insumo_transactions` guarda `quantity`, não valor. O preço por unidade mora em
`insumos.cost_per_unit`, então esta função **recebe o insumo junto**, não separado:

```python
compras_insumo = [
    {"quantity": 50, "transaction_date": "2026-08-01",
     "insumo": {"name": "Ração", "cost_per_unit": 2.30}},
    ...
]
```

Documente essa decisão de formato no docstring — é a parte da spec mais fácil de
implementar diferente do que se espera.

## Regras que decidem a correção

**Hoje o sistema não tem "a prazo".** Toda venda e todo custo já registrados têm data
única — não existe `due_date` separado de `paid_date` em nenhuma das quatro tabelas.
Por isso `competencia == vencimento == pagamento` na normalização atual: **nada fica em
aberto**, e `em_aberto()` do `caixa.py` sempre devolveria lista vazia com os dados de
hoje. Isso não é bug seu — é limitação real dos dados, e o teste correspondente
(`test_tudo_e_reconhecido_a_vista`) prova exatamente isso, não o contrário.

**`amount` negativo em `fixed_costs`/`animal_costs` é estorno, não erro.** Mantenha o
sinal — `caixa.py` já soma despesas como positivas e o service de rateio (spec 0031)
provou que valor negativo precisa preservar o módulo. Não normalize para `abs()`.

**Categoria ausente vira string vazia, nunca `None`** — `caixa.py` usa `categoria` como
chave de agrupamento, e `None` quebraria a ordenação por string que ele já faz.

## Critério de aceite

1. Uma venda de R$ 3000 em 2026-08-01 gera um lançamento `receita`/`venda`/R$ 3000,
   com as três datas iguais a `2026-08-01`.
2. Um custo fixo negativo (estorno de R$ -200) mantém o sinal no lançamento.
3. Uma linha de `insumo_transactions` com `type="consumo"` **não** gera lançamento.
4. Uma compra de insumo sem `insumo` embutido (ou sem `cost_per_unit`) não estoura —
   decida o que fazer (ignorar a linha? valor 0?) e **justifique no PR**.
5. As quatro listas vazias devolvem lista vazia.
6. O resultado de `normalizar(...)` passado direto para
   `services.caixa.resultado_por_competencia(...)` produz `receitas - despesas ==
   resultado` para qualquer combinação — é o "teste do centavo" da spec 0031, agora
   verificado ponta a ponta com dados que passaram por esta função.

## Proibições

- ❌ **Nenhum `SELECT`.** As quatro listas chegam prontas; se você sentir vontade de
  consultar o banco, é sinal de que o contrato está errado — pare e reveja.
- ❌ Não altere `services/caixa.py`. Ele está correto; o problema era a entrada, não ele.
- ❌ Não invente uma quinta fonte de dinheiro que não esteja listada acima.
- ❌ Não toque em `database.py`, `repositories/`, `app.py`.

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t .
git diff --stat origin/main
```

## Entrega

PR para `main`. No corpo, mostre a saída de `normalizar()` para um mês fictício com uma
venda, um custo fixo, um custo de animal e uma compra de insumo — e o resultado de
`caixa.resultado_por_competencia()` sobre essa saída, para provar que os dois módulos se
encaixam.
