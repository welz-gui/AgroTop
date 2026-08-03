# Spec 0018 — Previsão de ruptura de estoque (função pura)

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 1 dia
- **Branch:** `feat/previsao-estoque`
- **Crie:** `services/previsao_estoque.py` e `tests/test_previsao_estoque.py` — **arquivos novos**

---

## Regra de ouro desta spec

Você cria **arquivos novos**. **Não altere nenhum arquivo existente.** Seu produto é uma
função pura, testada, com contrato fixo — o mantenedor liga à interface e ao banco depois
(ROADMAP R31).

## Objetivo

Hoje o alerta de estoque é binário: abaixo do mínimo ou não. Isso avisa **quando já é
tarde** — o pecuarista descobre que o sal acabou no dia em que acabou.

Esta função responde **quantos dias faltam** para cada insumo acabar, no ritmo de consumo
observado, e qual a data provável de ruptura. É o que transforma o alerta em decisão de
compra com antecedência.

## Contrato obrigatório

```python
def prever(insumos: list[dict], hoje: str) -> list[dict]:
    """Dias restantes e data de ruptura por insumo.

    `insumos`: [{
        "id": int, "nome": str, "unidade": str,
        "saldo": float,
        "consumo_diario": float,      # média observada; 0 = sem consumo conhecido
        "estoque_minimo": float,
        "prazo_reposicao_dias": int,  # da compra até chegar; 0 se desconhecido
    }, ...]
    `hoje`: "AAAA-MM-DD"

    Retorna, ordenado do mais urgente ao menos:
        [{
          "id": int, "nome": str,
          "dias_restantes": float | None,   # None = consumo desconhecido
          "data_ruptura": str | None,       # "AAAA-MM-DD"
          "comprar_ate": str | None,        # data_ruptura menos prazo_reposicao
          "urgencia": "critica" | "atencao" | "ok" | "sem_dados",
        }, ...]
    """
```

**Assine exatamente assim.**

## Regras de urgência

| Urgência | Quando |
|---|---|
| `critica` | já passou de `comprar_ate`, ou saldo abaixo do mínimo |
| `atencao` | faltam 15 dias ou menos até `comprar_ate` |
| `ok` | acima disso |
| `sem_dados` | `consumo_diario` é 0 ou ausente |

**`sem_dados` não é `ok`.** São coisas diferentes: um insumo sem consumo registrado pode
estar acabando sem ninguém saber. Confundir os dois esconde exatamente o caso perigoso.

## Critério de aceite

1. Insumo com saldo 100 e consumo 10/dia devolve `dias_restantes = 10.0`.
2. Com `prazo_reposicao_dias = 7`, o `comprar_ate` fica 7 dias **antes** da ruptura.
3. Consumo zero devolve `sem_dados`, **não** `ok`, e `dias_restantes = None`.
4. Divisão por zero não estoura em nenhum caminho.
5. A ordenação coloca `critica` antes de `atencao`, e nunca `sem_dados` no fim silenciosamente
   — decida e **justifique no PR** onde `sem_dados` entra na ordem.

## Proibições

- ❌ Não toque em `app.py`, `database.py`, `repositories/`, `ui/`, nem em módulo existente
  de `services/`.
- ❌ **Não consulte banco.** Todos os dados entram por parâmetro — é o que torna a função
  testável sem fixture e reaproveitável na API e no mobile depois.
- ❌ Não crie tabela nem migration (R4: schema é do mantenedor).
- ❌ Não integre à interface.
- ❌ Não adicione dependência ao `requirements.txt` da raiz sem justificar no PR.

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t .
git diff --stat origin/main
```

O `-t .` não é opcional (R16) e o `AGROTOP_FORCE_SQLITE=1` é a segunda trava — sem os dois,
os testes podem conectar no banco de produção. No diff, só os dois arquivos novos.

## Entrega

PR para `main`, pronto para revisão. No corpo, diga onde você colocou `sem_dados` na ordenação e por quê.
