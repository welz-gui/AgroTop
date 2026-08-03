# Spec 0021 — Competência × caixa e fluxo projetado (função pura)

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 2 dias
- **Branch:** `feat/competencia-caixa`
- **Crie:** `services/caixa.py` e `tests/test_caixa.py` — **arquivos novos**

---

## Regra de ouro desta spec

Você cria **arquivos novos**. **Não altere nenhum arquivo existente.**

## Objetivo

O ROADMAP diz, na Trilha 3: *"nunca misturar competência, vencimento e data de caixa — é
onde nascem os bugs de DRE"*. Esta função existe para tornar essa separação **explícita e
testada antes** de o módulo financeiro ser construído em cima dela.

## As três datas, que não são a mesma

| Data | O que significa | Responde |
|---|---|---|
| **competência** | quando o fato econômico ocorreu | quanto custou o mês |
| **vencimento** | quando a obrigação vence | o que devo esta semana |
| **caixa** | quando o dinheiro saiu ou entrou | quanto tenho hoje |

Uma compra de ração feita em 30/03, com vencimento em 30/04 e paga em 05/05, aparece em
**três meses diferentes** conforme a pergunta. Um DRE que soma pela data errada mente — e
mente de um jeito que ninguém percebe até o contador conferir.

## Contrato obrigatório

```python
def resultado_por_competencia(lancamentos: list[dict], ano: int, mes: int) -> dict:
    """DRE gerencial do mês: soma pela data de COMPETÊNCIA.

    `lancamentos`: [{
        "tipo": "receita" | "despesa",
        "categoria": str,
        "valor": float,                     # sempre positivo
        "competencia": "AAAA-MM-DD",
        "vencimento": "AAAA-MM-DD" | None,
        "pagamento": "AAAA-MM-DD" | None,   # None = em aberto
    }, ...]

    Retorna {"receitas": float, "despesas": float, "resultado": float,
             "por_categoria": [{"categoria": str, "valor": float}, ...]}
    """


def fluxo_de_caixa(lancamentos: list[dict], de: str, ate: str) -> dict:
    """Realizado (pela data de pagamento) e projetado (pelo vencimento em aberto).

    Retorna {"realizado": float, "projetado": float, "saldo_projetado": float}
    """


def em_aberto(lancamentos: list[dict], hoje: str) -> list[dict]:
    """Contas sem pagamento, com dias de atraso. Vencidas primeiro."""
```

**Assine exatamente assim.**

## Critério de aceite

1. **O teste central desta spec:** um lançamento com competência em março, vencimento em
   abril e pagamento em maio aparece no resultado de **março** e no realizado de **maio**.
   O **mesmo lançamento ainda em aberto** (sem `pagamento`) aparece no projetado de
   **abril**. Se esses dois testes passam, a separação está correta.

   ⚠️ **Correção de 2026-08-03:** a versão anterior deste critério dizia que o lançamento
   *já pago* deveria aparecer no projetado de abril — o que contradizia o próprio contrato,
   que define projetado como "vencimento **em aberto**". Não se projeta pagamento que já
   aconteceu. O contrato estava certo; o critério é que estava mal escrito.
2. Lançamento sem `pagamento` **nunca** entra no realizado.
3. `em_aberto` calcula o atraso corretamente e **não** conta como atrasado o que vence hoje.
4. Mês sem lançamento devolve zeros, não erro.
5. Despesa é somada como valor positivo em `despesas`; o sinal aparece só em `resultado`.
6. Lançamento com data malformada é ignorado com registro, não derruba o cálculo — um
   relatório que estoura por causa de uma linha ruim é inútil no fechamento do mês.

## Proibições

- ❌ Não toque em `app.py`, `database.py`, `repositories/`, `ui/`, nem em módulo existente
  de `services/`.
- ❌ **Não consulte banco.** Tudo entra por parâmetro.
- ❌ Não crie tabela nem migration (R4).
- ❌ Não integre à interface.
- ❌ **Não implemente regime de competência contábil completo** (depreciação, provisão,
  rateio de exercício). O escopo é gerencial: três datas, três leituras.

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t .
git diff --stat origin/main
```

## Entrega

PR para `main`, pronto para revisão. No corpo, cole o teste da compra que aparece em três
meses diferentes.
