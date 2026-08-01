# Spec 0016 — Indicador de completude de dados (função pura)

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 1 dia
- **Branch:** `feat/completude-dados`
- **Crie:** `services/completude.py` e `tests/test_completude.py` — **arquivos novos**

---

## Regra de ouro desta spec

Você cria **arquivos novos**. **Não altere nenhum arquivo existente.**

## Objetivo

A PoC 0006 mostrou que os modelos preditivos batem a linha de base ingênua **com 3 meses**
de coleta, e que 12 meses contínuos dão um piloto sazonal. Mas isso vale só se a coleta for
**regular** — e hoje não há como saber se está sendo.

Esta função responde, mês a mês: **a base está ficando treinável, ou está com buracos?**

O valor não é o modelo futuro. É imediato: um piquete que parou de ser pesado, ou pesagens
chegando sem `lote_id`, são problemas de manejo que aparecem aqui antes de virarem decisão
errada.

## Contrato obrigatório

```python
def avaliar_mes(
    ano: int,
    mes: int,
    animais_ativos: int,
    pesagens: list[dict],       # [{"animal_id","data","lote_id","method"}, ...]
                                # já filtradas ao mês
    dias_lote_planejados: int,
    dias_lote_executados: int,
    semanas_com_chuva: int,
    semanas_no_mes: int,
) -> dict:
    """Indicadores de completude de um mês. Nada de banco aqui — tudo injetado.

    Retorna:
        {
          "animais_com_pesagem_em_dia": float,   # 0..1
          "intervalos_uteis_gmd":       float,
          "contexto_da_pesagem":        float,
          "execucao_nutricional":       float,
          "cobertura_ambiental":        float,
          "alertas": [{"indicador": str, "valor": float,
                       "minimo": float, "mensagem": str}, ...],
        }
    """
```

**Assine exatamente assim.**

## Os cinco indicadores e seus limiares

Vieram do painel proposto pela PoC 0006 — use estes valores como mínimo aceitável:

| Indicador | Cálculo | Mínimo |
|---|---|---|
| `animais_com_pesagem_em_dia` | ativos com pesagem nos últimos 60 dias ÷ ativos | 0,80 |
| `intervalos_uteis_gmd` | animais com duas pesagens válidas em 30–60 dias ÷ ativos | 0,70 |
| `contexto_da_pesagem` | pesagens com `lote_id` **e** `method` preenchidos ÷ pesagens | 0,95 |
| `execucao_nutricional` | dias-lote com execução ÷ dias-lote planejados | 0,90 |
| `cobertura_ambiental` | semanas com registro de chuva ÷ semanas do mês | 0,90 |

`alertas` traz **um item por indicador abaixo do mínimo**, com mensagem em português
dizendo o que fazer — não só que está baixo.

## Critério de aceite

1. Mês completo e regular → todos os indicadores em 1,0 e `alertas` vazio.
2. Mês com metade dos animais sem pesagem → `animais_com_pesagem_em_dia` = 0,5 e alerta
   correspondente presente.
3. **Divisão por zero não estoura**: mês sem animais ativos, sem pesagens, sem dias-lote
   planejados e sem semanas. Decida o que devolver nesse caso e **justifique no PR** — zero
   e "sem dados" são respostas diferentes, e a escolha muda como o painel lê o mês.
4. `intervalos_uteis_gmd` conta o animal uma vez, mesmo com muitas pesagens.

## Proibições

- ❌ Não toque em `app.py`, `database.py`, `services/` existentes, `repositories/`, `ui/`.
- ❌ Não consulte banco: **todos os números entram por parâmetro.** É o que torna a função
  testável sem fixture e reaproveitável na API depois.
- ❌ Não crie tabela nem migration.
- ❌ Não integre à interface.
- ❌ Não adicione dependência ao `requirements.txt` da raiz — isto é aritmética.

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t .
git diff --stat origin/main
```

## Entrega

PR para `main`. No corpo, diga **o que você decidiu para o mês sem dado nenhum** e por quê.
