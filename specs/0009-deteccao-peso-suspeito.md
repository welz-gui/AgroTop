# Spec 0009 — Detecção de pesagem suspeita (função pura)

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 1 dia
- **Branch:** `feat/qualidade-pesagem`
- **Crie:** `services/qualidade.py` e `tests/test_qualidade.py` — **arquivos novos**

---

## Regra de ouro desta spec

Você cria **arquivos novos**. **Não altere nenhum arquivo existente.** Seu produto é uma
função pura, testada, com contrato claro — o mantenedor liga à interface depois.

## Objetivo

Peso errado entra em silêncio e contamina tudo a jusante: GMD, projeção de abate, custo por
arroba, ranking de fornecedor. Um "450" digitado como "4500" vira decisão errada de venda.

Esta função **não corrige nem bloqueia** — ela **avisa**, para o operador confirmar. No
campo, com luva e sol, o custo de bloquear indevidamente é alto.

## Contrato obrigatório

```python
def avaliar_pesagem(
    peso: float,
    data: str,                 # "AAAA-MM-DD"
    historico: list[dict],     # [{"peso": float, "data": "AAAA-MM-DD"}, ...]
                               # ordenado da mais recente para a mais antiga
) -> list[dict]:
    """Aponta indícios de erro numa pesagem, sem bloquear.

    Retorna lista de alertas (vazia = nada suspeito):
        [{"tipo": str, "severidade": "alta"|"media", "mensagem": str}, ...]

    `historico` é injetado — a função não consulta o banco.
    """
```

**Assine exatamente assim.**

## Detecções obrigatórias

| tipo | Quando | Severidade |
|---|---|---|
| `fora_de_faixa` | peso ≤ 0 ou > 1500 kg | alta |
| `variacao_absurda` | variação > 20 % em relação à última pesagem | alta |
| `gmd_implausivel` | GMD desde a última pesagem fora de −1,0 a +3,0 kg/dia | alta |
| `perda_de_peso` | peso menor que o anterior, mas dentro dos limites acima | média |
| `duplicidade` | já existe pesagem na **mesma data** no histórico | média |
| `data_futura` | data posterior a hoje | alta |

**Sem histórico** (animal novo), só as detecções que não dependem dele: `fora_de_faixa` e
`data_futura`.

As mensagens são lidas por um operador no celular: escreva em português claro, com o
número que motivou o alerta. Exemplo: `"Ganho de 87 kg em 12 dias (7,25 kg/dia) — confira
se o peso está correto."`

## Cuidado com o cálculo de GMD

A regra de GMD do projeto já existe e **não deve ser reimplementada**
([ROADMAP.md](../ROADMAP.md) R8). Aqui o cálculo é diferente e local — entre a pesagem
sendo avaliada e a última do histórico —, então **calcule inline**, sem importar
`services.zootecnia`, e **documente no docstring** que não é o mesmo GMD exibido no app.

## Testes obrigatórios

`tests/test_qualidade.py`: cada tipo de detecção isoladamente, caso limpo (lista vazia),
animal sem histórico, múltiplos alertas simultâneos, e as fronteiras exatas (20,0 % e
20,1 %; GMD 3,0 e 3,1).

## Critério de aceite

1. Contrato respeitado exatamente.
2. Cada tipo de detecção tem teste, incluindo as fronteiras.
3. `services/qualidade.py` não importa `streamlit`, `database`, `repositories` nem driver
   de banco (R9).
4. Suíte verde.

## Proibições

- ❌ Não altere arquivo existente.
- ❌ Não **bloqueie** a pesagem: a função só avisa. Decisão é do operador.
- ❌ Não importe `services.zootecnia` para GMD — o cálculo aqui é outro (ver acima).
- ❌ Não toque no banco nem na interface.
- ❌ Não adicione dependência.

## Como verificar antes de abrir o PR

```bash
python -m unittest discover -s tests -t . -v
git diff --stat origin/main    # apenas os 2 arquivos novos
```

## Entrega

PR para `main` com exemplos de mensagem geradas — elas serão lidas no celular, no sol, e a
clareza do texto é parte da entrega.
