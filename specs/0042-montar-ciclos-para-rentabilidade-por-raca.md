# Spec 0042 — Montar ciclos encerrados para `services/rentabilidade.py`

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 1 dia
- **Branch:** `feat/montar-ciclos-rentabilidade`
- **Crie:** `services/rentabilidade_adaptador.py` e
  `tests/test_rentabilidade_adaptador.py` — **arquivos novos**

---

## Regra de ouro desta spec

Você cria **um arquivo novo**. **Não altere `services/rentabilidade.py`** — a margem
negativa dele já foi corrigida uma vez (histórico no ROADMAP: "spec 0017 dizia margem
0..1, e clamping fazia raça com prejuízo mostrar 0.0"). Ele está correto.

## Contexto

`services/rentabilidade.py::ranking_por_raca(ciclos)` agrupa por raça e calcula lucro por
cabeça, lucro por arroba e GMD médio — mas só de **ciclos encerrados**, isto é, animais
que já foram vendidos. Espera:

```python
[{"raca": str, "peso_entrada": float, "peso_saida": float,
  "custo_total": float, "receita": float | None, "dias": int}, ...]
```

A página **🏆 Origem** de `page_financeiro` já faz uma agregação parecida — por
`fornecedor`, via `db.get_fornecedor_ranking()` — mas agrupada por origem, não por raça,
e essa consulta mora em `database.py`, não em `services/`. Esta spec não toca nela; monta
a lista de ciclos a partir das mesmas fontes cruas (`sales`, `animals`, custo por animal).

## Objetivo

Uma função pura que junta uma venda com os dados do animal vendido e o custo total dele,
produzindo um ciclo no formato que `rentabilidade.py` espera.

## Contrato obrigatório

```python
def montar_ciclos(
    vendas: list[dict],
    # linhas de `sales`: {"animal_uuid": str, "sale_date": str, "total_value": float}
    animais_por_uuid: dict[str, dict],
    # {uuid: {"breed": str, "entry_weight": float, "current_weight": float,
    #         "entry_date": str}}
    custo_total_por_uuid: dict[str, float],
    # {uuid: custo acumulado do animal — já vem pronto de db.get_total_cost, repassado
    #  por quem chama}
) -> list[dict]:
    """Um ciclo por venda. Venda cujo `animal_uuid` não está em `animais_por_uuid`
    é ignorada (dado inconsistente, não deveria acontecer — não é erro para estourar).

    `peso_saida` é o `current_weight` do animal **no momento da venda**. Hoje o sistema
    não guarda peso histórico por venda — usa o peso atual do cadastro como proxy. Isso
    é impreciso se o animal foi pesado de novo depois da venda (não deveria acontecer
    num fluxo correto, mas documente a limitação no docstring).

    `dias` é `(sale_date - entry_date).days`, nunca negativo (mesma regra da spec 0041).

    `receita` é sempre `total_value` da venda — nunca `None` aqui, porque só entram
    ciclos de vendas que de fato aconteceram. `rentabilidade.py` já trata `receita is
    None` como "ciclo sem desfecho" para outros chamadores possíveis; esta função nunca
    produz esse caso.
    """
```

## Regras que decidem a correção

**Uma venda == um ciclo, sempre.** Não agrupe vendas do mesmo animal (não deveria haver
duas vendas do mesmo `animal_uuid` — se houver, é dado inconsistente da import/migração;
trate como dois ciclos separados, não some).

**`custo_total_por_uuid` ausente para um `animal_uuid` vira custo `0.0`, não motivo para
descartar a venda.** Animal sem nenhum custo lançado é raro mas legítimo (comprado e
vendido rápido sem nenhum lançamento); o lucro dele é a receita cheia, e é informação
real, não erro.

## Critério de aceite

1. Uma venda com animal e custo presentes produz um ciclo com todos os campos corretos.
2. Venda cujo `animal_uuid` não está em `animais_por_uuid` não aparece no resultado.
3. Venda cujo `animal_uuid` não está em `custo_total_por_uuid` produz ciclo com
   `custo_total=0.0`, não é descartada.
4. Duas vendas do mesmo animal produzem dois ciclos.
5. `dias` nunca é negativo, mesmo com `entry_date` posterior a `sale_date` por erro de
   dado.
6. O resultado, passado para `rentabilidade.ranking_por_raca()`, produz margem negativa
   (não zero) para uma raça cujo custo total supera a receita — é a garantia de que o
   defeito histórico do clamping não volta por um caminho novo.

## Proibições

- ❌ Não altere `services/rentabilidade.py`.
- ❌ Não toque em `database.get_fornecedor_ranking` nem em nenhuma consulta existente.
- ❌ Não consulte banco.
- ❌ Não toque em `database.py`, `repositories/`, `app.py`.

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t .
git diff --stat origin/main
```

## Entrega

PR para `main`. No corpo, 4 vendas fictícias de raças diferentes (uma delas com prejuízo)
e o ranking final de `rentabilidade.ranking_por_raca()` sobre a saída de `montar_ciclos()`.
