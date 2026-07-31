# Spec 0010 — Custo médio ponderado de insumo (função pura + decisão)

- **Tipo:** implementação + decisão · **Risco:** baixo no código, **alto na decisão**
- **Esforço:** 1–2 dias · **Branch:** `feat/custo-medio-ponderado`
- **Crie:** `services/estoque.py` e `tests/test_estoque_custo.py` — **arquivos novos**

---

## Regra de ouro desta spec

Você cria **arquivos novos**. **Não altere nenhum arquivo existente** — em especial
`database.py`, onde vive `add_insumo_entry`. A troca do comportamento atual é feita pelo
mantenedor, depois, e de forma consciente.

Esta é a **única tarefa da fila que avança a Trilha 3** (Estoque → Financeiro → Nutrição),
que hoje não tem nenhuma cobertura.

## O problema real

Hoje o custo unitário do insumo é **sobrescrito** pela última entrada:

```sql
UPDATE insumos SET current_stock = current_stock + ?, cost_per_unit = ? WHERE id = ?
```

Isso já está documentado como comportamento atual em `tests/test_regras_negocio.py`
(`test_entrada_soma_estoque_e_atualiza_custo`, marcado com `QUIRK:`).

Consequência: comprar 10 kg a R$ 5 quando havia 1.000 kg a R$ 2 faz **todo** o estoque
passar a valer R$ 5/kg. O custo de trato, o custo por animal e a margem saem inflados.

## Parte 1 — A função

```python
def custo_medio_ponderado(
    saldo_atual: float,
    custo_atual: float,
    quantidade_entrada: float,
    custo_entrada: float,
) -> float:
    """Novo custo unitário após uma entrada, ponderado pelas quantidades.

    (saldo_atual × custo_atual + quantidade_entrada × custo_entrada)
    ÷ (saldo_atual + quantidade_entrada)

    Arredondar para 2 casas.
    """
```

Casos que **precisam** estar tratados e testados:

- estoque zerado (`saldo_atual = 0`) → o custo passa a ser o da entrada;
- **estoque negativo** — existe na prática, por baixa lançada antes da compra. Decida o
  tratamento e **justifique no PR**;
- entrada com quantidade zero → custo inalterado, sem divisão por zero;
- custo de entrada zero (doação, brinde) → é entrada válida, não erro;
- valores que geram dízima → conferir o arredondamento.

## Parte 2 — A decisão (é o mais importante desta spec)

Adotar média ponderada **altera custo histórico já lançado**. É preciso decidir e
documentar, em `docs/adr/0003-custo-medio-ponderado.md`:

1. **Vale retroativo ou só para entradas novas?** Retroativo muda margem de vendas já
   registradas — relatórios que o usuário já leu passariam a mostrar outro número.
2. **Se não for retroativo, como fica o histórico misto?** Parte a custo sobrescrito,
   parte a custo médio. Isso precisa ser explicável para quem lê o relatório.
3. **Qual o efeito sobre `animal_costs` já gravado?** Aqueles registros guardam valor
   absoluto, não referência ao insumo — verifique e diga se são afetados.

Siga o formato dos ADRs existentes (`docs/adr/0001` e `0002`): contexto com evidência,
decisão, consequências, alternativas consideradas.

**Recomendação para a decisão:** prefira **não retroativo**, salvo se encontrar motivo
forte. Alterar número que o usuário já usou para decidir venda é grave — e o
[ROADMAP.md](../ROADMAP.md) seção 3 trata resultado numérico como comportamento a preservar.
Mas a decisão é sua de propor; justifique.

## Testes obrigatórios

`tests/test_estoque_custo.py`: cálculo normal, cada caso limite acima, e um cenário de
três entradas sequenciais mostrando a média evoluindo.

## Critério de aceite

1. Função com o contrato acima, todos os casos limite testados.
2. ADR escrito, com recomendação clara sobre retroatividade.
3. `services/estoque.py` não importa `streamlit`, `database` nem driver de banco (R9).
4. Suíte verde.

## Proibições

- ❌ **Não altere `add_insumo_entry` nem qualquer arquivo existente.** A troca é decisão do
  mantenedor, depois de ler o seu ADR.
- ❌ Não altere `tests/test_regras_negocio.py` — o `QUIRK` documenta o comportamento atual
  e continua correto até a troca acontecer.
- ❌ Não crie migration nem toque no schema (R4).
- ❌ Não adicione dependência.

## Como verificar antes de abrir o PR

```bash
python -m unittest discover -s tests -t . -v
git diff --stat origin/main    # 2 arquivos novos + o ADR
```

## Entrega

PR para `main` abrindo pela recomendação sobre retroatividade em uma frase. O código é a
parte fácil; **a decisão é a entrega**.
