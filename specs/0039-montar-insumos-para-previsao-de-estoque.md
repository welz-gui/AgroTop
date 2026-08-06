# Spec 0039 — Montar a lista de insumos que `services/previsao_estoque.py` espera

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 1-2 dias
- **Branch:** `feat/montar-insumos-previsao`
- **Crie:** `services/previsao_estoque_adaptador.py` e
  `tests/test_previsao_estoque_adaptador.py` — **arquivos novos**

---

## Regra de ouro desta spec

Você cria **um arquivo novo**. **Não altere `services/previsao_estoque.py`.**

## Contexto

`services/previsao_estoque.py::prever(insumos, hoje)` calcula dias até a ruptura de cada
insumo. Espera:

```python
[{"id": int, "nome": str, "saldo": float, "consumo_diario": float,
  "estoque_minimo": float, "prazo_reposicao_dias": int}, ...]
```

`insumos` (a tabela) tem `current_stock` (→ `saldo`) e `min_stock` (→ `estoque_minimo`)
prontos. O que falta:

- **`consumo_diario`** não é uma coluna — precisa ser calculado.
- **`prazo_reposicao_dias`** não existe em lugar nenhum do schema.

`app.py` já resolve `consumo_diario` de um jeito, hoje, só que **dentro de uma função
privada** (`_consumo_diario_por_insumo`, perto da linha 2468) que alimenta o motor de
recomendações. Ela usa consumo **planejado** (a soma dos planos de trato ativos), não
consumo **observado** (o que realmente saiu do estoque em `insumo_transactions`). Isso é
uma decisão válida — só que hoje ela está presa em `app.py`, onde nenhum outro módulo
consegue reaproveitá-la, e o R8 do ROADMAP diz que regra de negócio não deveria morar lá.

## Objetivo

Duas funções: uma que extrai o mesmo cálculo de consumo planejado para `services/`, de
forma reaproveitável e testável; outra que monta a lista final para `prever()`.

## Contrato obrigatório

```python
def consumo_diario_planejado(
    insumos_por_id: dict[int, dict],   # {id: {"unit": str}}
    planos_ativos: list[dict],
    # linhas de feeding_plans com active=True: {"insumo_id": int, "quantity": float,
    #  "unit": str, "frequency": str}
    converter_quantidade,
    # a própria `database.convert_quantity` (hoje mora lá, não em services/) — recebida
    # como PARÂMETRO, não importada: este módulo não pode importar `database.py` (R9,
    # services/ não depende da camada de dados), então quem chama injeta a função,
    # mesmo padrão de injeção de dependência usado na spec 0031
) -> dict[int, float]:
    """{insumo_id: kg ou litro por dia}. Plano cuja unidade não converte para a do
    insumo é ignorado — mesma regra do `_consumo_diario_por_insumo` que isto substitui.
    Frequência desconhecida: mesma decisão tomada na spec 0037, para as duas ficarem
    consistentes entre si.
    """


def montar_insumos(
    insumos: list[dict],
    # linhas de `insumos`: {"id": int, "name": str, "unit": str,
    #  "current_stock": float, "min_stock": float}
    consumo_por_id: dict[int, float],   # saída de consumo_diario_planejado()
    prazos_de_reposicao: dict[int, int] = None,
    # {insumo_id: dias} -- opcional; ver "Sobre o prazo de reposição" abaixo
) -> list[dict]:
    """Monta a lista final para services.previsao_estoque.prever()."""
```

## Sobre o prazo de reposição

Não existe coluna para isso. `prazos_de_reposicao` é opcional e, para qualquer insumo
ausente do dict (inclusive quando o parâmetro inteiro é `None`), use `0` —
**exatamente o que `previsao_estoque.prever()` já assume como "desconhecido"** (leia o
módulo: `prazo_reposicao_dias=0` já é tratado como caso válido, não como erro). Não
proponha a coluna nova; é decisão de schema, fora do escopo.

## Regras que decidem a correção

**Não recalcule o que `previsao_estoque.py` já decide.** Sua função só monta a lista de
entrada; urgência, data de ruptura e ordenação são todos calculados **dentro** de
`prever()`. Se você se pegar calculando "dias restantes" aqui, está duplicando R8.

**Insumo sem nenhum plano ativo tem `consumo_diario=0.0`, não ausência.** É consumo
zero conhecido — diferente de "não sei quanto consome", que `previsao_estoque.py`
trata como `urgencia="sem_dados"` só quando `consumo_diario <= 0` **e** não há como
saber. Zero é uma resposta válida aqui: "não há plano de trato para isto".

## Critério de aceite

1. `consumo_diario_planejado` com um plano diário de 2 kg/dia devolve `2.0` para aquele
   insumo.
2. Plano com unidade incompatível com a do insumo (ex.: `"saco"` vs `"kg"` sem conversão
   conhecida) não aparece no resultado — nem erra, nem soma zero por engano.
3. `montar_insumos` sem `prazos_de_reposicao` produz `prazo_reposicao_dias=0` para todos.
4. Insumo sem nenhum plano ativo aparece na lista final com `consumo_diario=0.0`.
5. O resultado de `montar_insumos()`, passado para `previsao_estoque.prever()`, produz
   `urgencia="critica"` para um insumo com `saldo < estoque_minimo`, coerente com a regra
   que já está em `prever()`.

## Proibições

- ❌ Não altere `services/previsao_estoque.py` nem `app.py` — inclusive não mexa em
  `_consumo_diario_por_insumo`; ela pode continuar existindo em paralelo até o
  mantenedor decidir trocar.
- ❌ Não proponha a coluna `prazo_reposicao_dias` — fora do escopo.
- ❌ Não calcule urgência, data de ruptura nem ordenação — isso é do `prever()`.
- ❌ Não consulte banco.
- ❌ Não toque em `database.py`, `repositories/`.

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t .
git diff --stat origin/main
```

## Entrega

PR para `main`. No corpo, mostre as duas funções encadeadas com `previsao_estoque.prever()`
para 3 insumos fictícios (um crítico, um ok, um sem consumo conhecido).
