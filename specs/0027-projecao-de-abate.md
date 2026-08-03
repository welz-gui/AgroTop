# Spec 0027 — Projeção de abate e correlação chuva × GMD (função pura)

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 1–2 dias
- **Branch:** `feat/projecao-abate`
- **Crie:** `services/projecao.py` e `tests/test_projecao.py` — **arquivos novos**

---

## Regra de ouro desta spec

Você cria **arquivos novos**. **Não altere nenhum arquivo existente.**

## Objetivo

Duas perguntas que o pecuarista faz o tempo todo e o sistema ainda não responde:

1. **Quando este animal chega ao peso de abate?** — decide contrato de venda e escala no
   frigorífico.
2. **A chuva explica a variação de ganho?** — o dado já existe (`pluviometria` + pesagens) e
   nunca foi cruzado.

## Contrato obrigatório

```python
def projetar_abate(peso_atual: float, peso_alvo: float, gmd: float,
                   hoje: str) -> dict:
    """Quando o animal atinge o peso-alvo, no ritmo atual.

    Retorna {
      "dias_restantes": int | None,
      "data_prevista": str | None,     # "AAAA-MM-DD"
      "situacao": "pronto" | "projetado" | "sem_ganho" | "perdendo_peso",
    }
    """


def projetar_lote(animais: list[dict], hoje: str) -> dict:
    """Projeção agregada de um lote.

    `animais`: [{"id", "peso_atual", "peso_alvo", "gmd"}, ...]

    Retorna {
      "prontos": int,
      "data_primeiro": str | None, "data_ultimo": str | None,
      "dias_ate_lote_completo": int | None,
      "sem_projecao": [str, ...],     # ids sem GMD utilizável
    }
    """


def correlacao_chuva_gmd(series: list[dict]) -> dict:
    """Relação entre chuva do período e ganho médio.

    `series`: [{"periodo": "AAAA-MM", "chuva_mm": float, "gmd_medio": float}, ...]

    Retorna {"coeficiente": float | None, "n": int, "interpretacao": str}
    """
```

**Assine exatamente assim.**

## O que essa spec exige de honestidade

**`sem_ganho` e `perdendo_peso` não são a mesma coisa que "faltam muitos dias".** GMD zero
não dá data — dá `None`. GMD negativo é um problema de manejo, e devolver uma data futura
enorme esconderia isso atrás de um número.

**A correlação não é causalidade, e o texto precisa dizer isso.** `interpretacao` deve ser
frase em português que descreva a força da relação **sem afirmar causa** — chuva e ganho
sobem juntos por muitas razões (pasto, temperatura, manejo sazonal). Com `n` pequeno,
diga que a amostra é pequena em vez de reportar um coeficiente alto como se fosse achado.

**Com menos de 3 períodos, `coeficiente` é `None`.** Correlação de dois pontos é sempre
perfeita e sempre inútil.

## Critério de aceite

1. Animal a 400 kg, alvo 500, GMD 1,0 → 100 dias, data 100 dias à frente.
2. Peso atual ≥ alvo → `pronto`, `dias_restantes = 0`.
3. GMD zero → `sem_ganho`, `data_prevista = None`. GMD negativo → `perdendo_peso`.
4. `projetar_lote` separa em `sem_projecao` quem não tem GMD utilizável, em vez de assumir
   um valor.
5. `correlacao_chuva_gmd` com 2 períodos devolve `coeficiente = None` e diz por quê.
6. Série com chuva constante (variância zero) não estoura — devolve `None`.

## Proibições

- ❌ Não toque em `app.py`, `database.py`, `repositories/`, `ui/`, nem em módulo existente
  de `services/`.
- ❌ **Não consulte banco.** Tudo entra por parâmetro.
- ❌ Não crie tabela nem migration.
- ❌ **Não use GMD projetado para estimar preço nem receita.** A projeção é de peso e data;
  misturar preço acrescenta uma incerteza que a função não pode justificar.
- ❌ Não adicione `numpy`/`scipy` só pela correlação — Pearson é aritmética de dez linhas.
  Se adicionar mesmo assim, justifique no PR.

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t .
git diff --stat origin/main
```

## Entrega

PR para `main`, pronto para revisão. No corpo, cole a `interpretacao` gerada para uma série
de 3 períodos e outra de 12 — elas devem soar diferentes em confiança.
