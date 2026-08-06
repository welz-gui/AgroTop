# Spec 0037 — Montar a lista de ingredientes que `services/dieta.py` espera

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 1 dia
- **Branch:** `feat/montar-ingredientes-dieta`
- **Crie:** `services/dieta_adaptador.py` e `tests/test_dieta_adaptador.py` —
  **arquivos novos**

---

## Regra de ouro desta spec

Você cria **um arquivo novo**. **Não altere `services/dieta.py`** — está correto.

## Contexto

`services/dieta.py::custo_por_cabeca_dia(ingredientes)` calcula o custo diário de trato
por cabeça e a participação de cada insumo no custo. Espera:

```python
[{"nome": str, "quantidade_kg_cabeca_dia": float,
  "custo_por_kg": float, "materia_seca_pct": float}, ...]
```

A fonte real é `feeding_plans` (um plano por piquete, não por cabeça) mais `insumos`
(onde mora o custo por unidade). Duas conversões precisam acontecer antes de chegar nesse
formato: **de piquete para cabeça**, e **de unidade do plano para kg**.

## Objetivo

Uma função pura que recebe os planos de um piquete e a lotação dele, e devolve a lista de
ingredientes por cabeça.

## Contrato obrigatório

```python
def ingredientes_por_cabeca(
    planos_do_piquete: list[dict],
    # linhas de feeding_plans: {"product_name": str, "insumo_id": int, "quantity": float,
    #  "unit": str, "frequency": str, "active": bool}
    insumos_por_id: dict[int, dict],
    # {id: {"name": str, "unit": str, "cost_per_unit": float,
    #       "materia_seca_pct": float}}  -- ver "Sobre matéria seca" abaixo
    cabecas_no_piquete: int,
) -> list[dict]:
    """Ignora plano inativo (`active=False`) e plano cujo `insumo_id` não está em
    `insumos_por_id`. Ignora plano cuja unidade não converte para a do insumo (mesma
    regra de `database.convert_quantity` — sem densidade não se converte saco em kg).

    `quantity` do plano é por PIQUETE por aplicação; `frequency` diz quantas vezes por
    dia (mesmo vocabulário de `_FREQ_POR_DIA` em app.py — confira os valores antes de
    supor). Divide pelo nº de cabeças para chegar em quantidade por cabeça por dia.
    """
```

## Sobre matéria seca

`insumos` não tem coluna `materia_seca_pct` — não existe hoje no schema. **Não invente a
coluna nem proponha migration aqui** (fora do escopo desta spec). Trate a ausência assim:
se `insumos_por_id[id]` não trouxer `materia_seca_pct`, use `0.0` e **documente no
docstring que isso zera `kg_materia_seca` no resultado até o dado existir** — é uma
limitação real dos dados, não um bug seu, no mesmo espírito da spec 0034 sobre "não
existe a prazo".

## Regras que decidem a correção

**`cabecas_no_piquete == 0` não pode gerar `ZeroDivisionError`.** Piquete vazio com plano
ativo é situação real (curral esperando lote novo) — devolva lista vazia, não estoure.

**Um piquete pode ter dois planos para o mesmo insumo** (ex.: sal mineral de manhã e à
tarde, planos separados). Some as quantidades por `insumo_id` antes de gerar a linha —
não devolva duas entradas com o mesmo `nome`, porque `dieta.custo_por_cabeca_dia` soma
participações por posição na lista, e duas linhas do mesmo insumo distorceriam o
`pct_custo` de cada uma sem juntar o que é do mesmo produto.

**Frequência desconhecida não deve assumir 1×/dia silenciosamente para um valor que
claramente não é diário** — se `frequency` não estiver no vocabulário conhecido, pule o
plano e registre (retorno ou log, sua escolha, documentada) em vez de supor.

## Critério de aceite

1. Piquete com um plano ativo (2 kg/cabeça/dia de ração a R$ 1,50/kg) e 20 cabeças
   devolve uma linha com `quantidade_kg_cabeca_dia` correto.
2. Dois planos do mesmo insumo no mesmo piquete somam antes de virar uma linha.
3. Plano inativo não aparece no resultado.
4. `cabecas_no_piquete=0` devolve lista vazia, sem exceção.
5. Insumo sem `materia_seca_pct` gera linha com esse valor 0.0, sem quebrar o restante.
6. O resultado, passado para `dieta.custo_por_cabeca_dia()`, produz `custo_dia` maior
   que zero para o cenário do item 1.

## Proibições

- ❌ Não altere `services/dieta.py`.
- ❌ Não proponha nem implemente a coluna `materia_seca_pct` em `insumos` — schema é
  fora do escopo.
- ❌ Não consulte banco.
- ❌ Não toque em `database.py`, `repositories/`, `app.py`.

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t .
git diff --stat origin/main
```

## Entrega

PR para `main`. No corpo, um piquete fictício com dois planos (um deles duplicado no
mesmo insumo) e a lista final que sai da função.
