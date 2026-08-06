# Spec 0035 — Adaptar dados reais para `services/completude.py`

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 1 dia
- **Branch:** `feat/adaptar-completude`
- **Crie:** `services/completude_adaptador.py` e
  `tests/test_completude_adaptador.py` — **arquivos novos**

---

## Regra de ouro desta spec

Você cria **um arquivo novo**. **Não altere nenhum código de produção**, inclusive
`services/completude.py` — ele está correto, o problema é só a entrada dele.

## Contexto

`services/completude.py::avaliar_mes` já existe, é pura, e nunca foi chamada. Ela pede:

```python
avaliar_mes(ano, mes, animais_ativos: int, pesagens: list[dict],
           dias_lote_planejados: int, dias_lote_executados: int,
           semanas_com_chuva: int, semanas_no_mes: int)
```

`pesagens` precisa ter, por item, `animal_id`, `data`, `lote_id`, `method` — mas a tabela
real é `weighings`, com `animal_uuid` (não `animal_id`), `weigh_date` (não `data`). E
`dias_lote_planejados/executados` e `semanas_com_chuva/no_mes` **não existem prontos em
lugar nenhum** — são derivados de `feeding_checks` e `pluviometria`.

## Objetivo

Duas funções pequenas e independentes, cada uma resolvendo uma das duas lacunas.

## Contrato obrigatório

```python
def normalizar_pesagens(pesagens_brutas: list[dict]) -> list[dict]:
    """
    `pesagens_brutas`: linhas de `weighings` — `animal_uuid`, `weight`, `weigh_date`,
    `lote_id`, `method`.

    Retorna no formato que `avaliar_mes` espera: [{"animal_id": ..., "data": ...,
    "lote_id": ..., "method": ...}, ...]. `animal_id` recebe o valor de `animal_uuid`
    — o nome do campo muda, o identificador usado é o mesmo (§4.1: uuid é a identidade).
    """


def janela_do_mes(
    ano: int, mes: int, *,
    checagens_de_trato: list[dict],   # linhas de feeding_checks no mês
    leituras_de_chuva: list[dict],    # linhas de pluviometria no mês
) -> dict:
    """
    Retorna {
        "dias_lote_planejados": int,   # nº de feeding_checks esperadas no mês
        "dias_lote_executados": int,   # nº com status == "feito"
        "semanas_com_chuva": int,      # semanas do mês com pelo menos 1 leitura > 0
        "semanas_no_mes": int,         # sempre 4 ou 5, calculado do calendário
    }
    """
```

## Regras que decidem a correção

**`dias_lote_planejados` é a contagem de registros em `feeding_checks` no mês, não os
dias do calendário.** Um plano de trato pode ser semanal, não diário — contar dias de
calendário superestimaria o planejado para qualquer plano que não seja diário.
`status` em `feeding_checks` vem de `database.FEEDING_CHECK_STATUS` (veja o módulo antes
de assumir os valores possíveis — não é só `"feito"`/`"nao_feito"`).

**Semana com chuva conta pela leitura, não pelo volume.** `rain_mm > 0` numa leitura já
conta a semana inteira como "com chuva" — não é sobre quanto choveu, é sobre se alguém
mediu chuva alguma naquela semana. `completude.py` já decide o que fazer com a proporção;
esta função só entrega o numerador e o denominador certos.

**Semana é ISO, calculada da data de leitura** (`read_date`), não do dia do mês —
use `date.isocalendar()[1]` e agrupe por semana do calendário, cruzando corretamente
os casos em que a última semana de um mês continua no mês seguinte (conte só as leituras
cuja `read_date` cai dentro do mês pedido; a semana ISO é só o agrupador).

**`semanas_no_mes` não é `len({semanas com leitura})`** — é quantas semanas ISO o mês
*tem*, existindo leitura ou não, porque é o denominador da proporção. Um mês de 31 dias
cruza 5 ou 6 semanas ISO dependendo de onde cai o primeiro dia; calcule certo, não
aproxime por `31 // 7`.

## Critério de aceite

1. `normalizar_pesagens` com uma pesagem de `weighings` real (com `animal_uuid`) produz
   um dict com `animal_id` igual ao `animal_uuid` original.
2. `janela_do_mes` com 4 `feeding_checks` no mês, 3 com status de sucesso, devolve
   `dias_lote_planejados=4, dias_lote_executados=3`.
3. `janela_do_mes` sem nenhuma leitura de chuva no mês devolve `semanas_com_chuva=0` e
   `semanas_no_mes` igual ao número real de semanas ISO que o mês cruza (não 0).
4. Fevereiro de um ano comum e fevereiro de ano bissexto podem ter `semanas_no_mes`
   diferentes — teste os dois.
5. As duas funções, encadeadas com `avaliar_mes`, produzem um resultado sem estourar
   para um mês fictício com dados variados (alguns indicadores acima do mínimo, outros
   abaixo, gerando pelo menos um alerta).

## Proibições

- ❌ Não altere `services/completude.py`.
- ❌ Não consulte banco — as listas chegam prontas.
- ❌ Não invente uma terceira função "auxiliar" fora do contrato acima — duas bastam.
- ❌ Não toque em `database.py`, `repositories/`, `app.py`.

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t .
git diff --stat origin/main
```

## Entrega

PR para `main`. No corpo, mostre a saída das duas funções para um mês fictício e o
resultado final de `avaliar_mes()` alimentado por elas.
