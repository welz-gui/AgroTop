# Spec 0029 — 🇧🇷 Escore de conformidade PNIB (função pura)

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 1–2 dias
- **Branch:** `feat/escore-conformidade`
- **Crie:** `services/conformidade.py` e `tests/test_conformidade.py` — **arquivos novos**

---

## Regra de ouro desta spec

Você cria **arquivos novos**. **Não altere nenhum arquivo existente.**

## Objetivo

A Fase B do projeto implementou identidade imutável, eventos, auditoria, genealogia,
propriedades, GTA, dispositivos e regras. Falta a pergunta que o produtor faz:

> **"Estou conforme? Se o fiscal chegar amanhã, o que ele acha?"**

Hoje a resposta exige abrir sete telas e somar de cabeça. Esta função responde com um
número e, mais importante, com **a lista do que falta**.

## Contrato obrigatório

```python
def avaliar(rebanho: dict, referencia: str) -> dict:
    """Escore de conformidade e pendências, por dimensão.

    `rebanho`: {
        "animais_ativos": int,
        "com_identificacao_oficial": int,
        "com_identificacao_manejo": int,
        "com_propriedade": int,
        "nascidos_sem_mae": int,
        "com_nascimento_estimado": int,
        "eventos_pendentes_sincronizacao": int,
        "movimentacoes_abertas_vencidas": int,
        "dispositivos_com_divergencia": int,
    }
    `referencia`: "AAAA-MM-DD" — a data pela qual julgar.

    Retorna {
      "escore": float,            # 0..100
      "faixa": "critico"|"atencao"|"bom"|"conforme",
      "dimensoes": [{"nome": str, "peso": float, "nota": float,
                     "faltam": int, "mensagem": str}, ...],
      "pendencias_criticas": [str, ...],
      "prazo_relevante": str | None,
    }
    """


def dimensoes_avaliadas() -> list[dict]:
    """As dimensões e seus pesos, para a interface explicar o cálculo."""
```

**Assine exatamente assim.**

## As dimensões e por que os pesos são desiguais

| Dimensão | Peso | Por quê |
|---|---:|---|
| Identificação oficial | 35 | é o núcleo do PNIB; sem ela nada mais importa |
| Propriedade definida | 15 | animal sem lugar não é rastreável |
| Vínculo materno | 15 | §7; nascido sem mãe quebra a cadeia |
| Sincronização em dia | 15 | registrar não é comunicar |
| Nascimento com data exata | 10 | estimada é aceita, mas pesa |
| Sem divergência de dispositivo | 10 | §5.3 |

**Somam 100.** Se você mudar os pesos, **justifique no PR** — eles são julgamento, não fato,
e quem vier depois precisa saber que foram escolhidos e por quem.

## ⚠️ O prazo é o que torna isto honesto

A identificação oficial só é **exigível para trânsito a partir de 01/01/2033** (§4.1). Um
rebanho 0 % identificado em 2026 **não está irregular** — está no prazo.

Portanto:

- antes de 2033, a dimensão "identificação oficial" **não pesa como falta**, e sim como
  **preparo**; o `prazo_relevante` informa a data;
- a partir de 2033, ela passa a pesar integralmente.

Reportar 35 % de escore hoje por causa de uma exigência que só vale daqui a sete anos seria
alarme falso — e alarme falso ensina o usuário a ignorar o painel.

## Critério de aceite

1. Rebanho perfeito devolve **100** e faixa `conforme`.
2. Rebanho 0 % identificado, avaliado em **2026**, não é `critico` por isso — e o
   `prazo_relevante` traz `2033-01-01`.
3. O mesmo rebanho, avaliado em **2033**, cai para faixa `critico`.
4. `dimensoes` sempre traz as seis, mesmo as com nota cheia — o usuário precisa ver o que
   está certo, não só o que falta.
5. Rebanho vazio (`animais_ativos = 0`) **não divide por zero**; decida o que devolver e
   **justifique no PR** — fazenda sem animal não é fazenda irregular.
6. `pendencias_criticas` traz frases acionáveis, não nomes de campo: "12 animais sem
   propriedade definida", não `"com_propriedade: 12"`.

## Proibições

- ❌ Não toque em `app.py`, `database.py`, `repositories/`, `ui/`, nem em módulo existente
  de `services/`.
- ❌ **Não consulte banco.** Os números entram por parâmetro — é o que permite a mesma
  função servir ao painel, à API e a um relatório agendado.
- ❌ Não crie tabela nem migration.
- ❌ **Não afirme conformidade legal.** O escore é indicador de gestão, e a mensagem precisa
  deixar isso claro. Dizer "você está conforme" é afirmação jurídica que um software não
  pode fazer.

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t .
git diff --stat origin/main
```

## Entrega

PR para `main`. No corpo, mostre o **mesmo rebanho avaliado em 2026 e em 2033**, com escores
diferentes — é o caso que prova que o prazo foi respeitado.
