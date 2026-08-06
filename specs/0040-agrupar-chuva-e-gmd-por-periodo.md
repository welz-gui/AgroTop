# Spec 0040 — Agrupar chuva e GMD por período para `services/projecao.py`

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 1-2 dias
- **Branch:** `feat/agrupar-chuva-gmd`
- **Crie:** `services/projecao_adaptador.py` e
  `tests/test_projecao_adaptador.py` — **arquivos novos**

---

## Regra de ouro desta spec

Você cria **um arquivo novo**. **Não altere `services/projecao.py`.**

## Contexto

`services/projecao.py::correlacao_chuva_gmd(series)` calcula a correlação entre chuva e
ganho de peso. Espera:

```python
[{"chuva_mm": float, "gmd_medio": float}, ...]   # um item por período
```

Ninguém monta essa lista hoje. As fontes são `pluviometria` (`read_date`, `rain_mm`,
`lote_id`) e `weighings` (`weigh_date`, `weight`, `animal_uuid`) — duas séries de eventos
soltos no tempo, que precisam virar períodos comparáveis.

**Nota — não confundir com `projetar_lote`:** a outra função pública de
`services/projecao.py`, `projetar_lote(animais, hoje)`, já recebe quase exatamente o que
`app.py::_contexto_recomendacoes()` monta hoje (`id`, `peso`, `peso_alvo`, `gmd`) — o
ajuste para ligá-la é pequeno o bastante para o mantenedor fazer direto na integração.
**Esta spec é só sobre `correlacao_chuva_gmd`**, que não tem nenhum equivalente hoje.

## Objetivo

Uma função pura que agrupa leituras de chuva e pesagens em períodos mensais e calcula o
GMD médio de cada período.

## Contrato obrigatório

```python
def series_mensais(
    leituras_de_chuva: list[dict],   # linhas de pluviometria
    pesagens: list[dict],            # linhas de weighings, ORDENADAS por weigh_date
) -> list[dict]:
    """
    Agrupa por mês-calendário (AAAA-MM). Para cada mês com AO MENOS UMA leitura de
    chuva E ao menos um par de pesagens consecutivas do mesmo animal dentro do mês
    (para calcular GMD), produz um item:

    [{"periodo": "AAAA-MM", "chuva_mm": float, "gmd_medio": float}, ...]

    `chuva_mm` é a soma das leituras do mês. `gmd_medio` é a média do GMD entre pares
    consecutivos de pesagem do mesmo animal, calculado só com pesagens que caem dentro
    do mesmo mês (não cruza a fronteira do mês — ver "Por que não cruzar o mês" abaixo).

    Meses sem chuva OU sem nenhum GMD calculável ficam DE FORA da lista — não entram
    como zero. `correlacao_chuva_gmd` exige n>=3 pontos REAIS; um mês fantasma com
    `gmd_medio=0.0` inventaria correlação que não existe.

    Retorna ordenado por `periodo`.
    """
```

## Por que não cruzar o mês

Um GMD calculado entre uma pesagem em 28/07 e outra em 03/08 mistura o efeito da chuva
de julho com o de agosto — a correlação perderia sentido, porque nenhum dos dois meses
seria o "dono" real daquele ganho. Descarte pares de pesagem que não caem no mesmo mês
para o cálculo de GMD deste agrupamento — é uma perda de dado aceitável, porque o
objetivo aqui é a correlação mensal, não o GMD de cada animal em si (isso já é
`db.calculate_gmd`, intocado).

## Regras que decidem a correção

**GMD entre duas pesagens é `(peso2 - peso1) / dias`, dias > 0.** Reuse essa fórmula —
não precisa importar nada, é aritmética de duas linhas, mas não a reimplemente errado
(a spec 0031 já provou por teste de propriedade que essa fórmula é simétrica ao trocar
a ordem das datas com sinal invertido; use-a como referência de comportamento esperado).

**Animal com só uma pesagem no mês não contribui GMD para aquele mês** — precisa de
**par**, não de pesagem isolada.

**`gmd_medio` do mês é a média simples dos GMDs de todos os pares/animais daquele mês**,
não ponderada por peso nem por quantidade de pesagens do animal.

## Critério de aceite

1. Um mês com 3 leituras de chuva somando 120mm e um animal com duas pesagens dentro do
   mês produz um item com `chuva_mm=120.0` e `gmd_medio` correto para aquele par.
2. Par de pesagens que cruza a fronteira do mês (uma em julho, outra em agosto) não
   contribui GMD a nenhum dos dois meses.
3. Mês com chuva mas sem nenhum GMD calculável **não aparece** na lista.
4. Mês com GMD calculável mas sem nenhuma leitura de chuva **não aparece** na lista.
5. Dois animais diferentes com pares de pesagem no mesmo mês: `gmd_medio` é a média dos
   dois, não a soma.
6. A saída, passada para `projecao.correlacao_chuva_gmd()`, não levanta exceção para
   0, 1, 2 e 5+ meses de dados.

## Proibições

- ❌ Não altere `services/projecao.py`.
- ❌ Não invente mês com dado zerado para "completar" a série.
- ❌ Não consulte banco.
- ❌ Não toque em `database.py`, `repositories/`, `app.py`.

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t .
git diff --stat origin/main
```

## Entrega

PR para `main`. No corpo, uma série fictícia de 4 meses (com um mês sem chuva e um sem
GMD, para provar que os dois somem) e a saída de `correlacao_chuva_gmd()` sobre o
resultado.
