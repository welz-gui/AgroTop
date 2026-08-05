# Spec 0028 — Lotação e sobreposição de piquetes (função pura)

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 1–2 dias
- **Branch:** `feat/geometria-lotacao-v2` — a `feat/geometria-lotacao` continua no
  remoto, ligada à PR fechada, e **não** deve ser reaproveitada.
- **Crie:** `services/lotacao.py` e `tests/test_lotacao.py` — **arquivos novos**
- **Estado:** 🔁 **retrabalho** — a [PR #82](https://github.com/welz-gui/AgroTop/pull/82)
  foi fechada com defeito confirmado. Leia a seção **"O defeito da primeira tentativa"**
  antes de começar: ela não é opcional, é o motivo desta spec estar de volta na fila.

---

## Regra de ouro desta spec

Você cria **arquivos novos**. **Não altere nenhum arquivo existente.** Pode **importar** de
`services/geometria.py` e `services/constantes.py` — reimplementar o que já existe viola a
R8.

## Objetivo

A spec 0015 entregou área e centroide a partir do polígono. Falta o que se faz com isso:

1. **Lotação em UA/ha** — quantas unidades-animal o piquete suporta e quantas tem.
2. **Sobreposição** — dois piquetes não podem ocupar o mesmo terreno, e hoje nada impede
   desenhar polígonos que se cruzam. Área somada maior que a fazenda é erro que passa
   despercebido até alguém conferir a conta.

## Contrato obrigatório

```python
def lotacao(area_ha: float, animais: list[dict]) -> dict:
    """Lotação atual do piquete.

    `animais`: [{"id": str, "peso": float}, ...]
    Uma UA = 450 kg de peso vivo (`services.constantes.UA_WEIGHT`).

    Retorna {
      "ua_total": float, "ua_por_ha": float,
      "cabecas": int, "peso_total": float,
    }
    """


def capacidade(area_ha: float, ua_por_ha_alvo: float) -> dict:
    """Quantas UA e cabeças o piquete comporta na lotação alvo.

    Retorna {"ua_suportadas": float, "cabecas_450kg": int}
    """


def avaliar_lotacao(area_ha: float, animais: list[dict],
                    ua_por_ha_alvo: float) -> dict:
    """Compara atual com alvo.

    Retorna {..., "situacao": "ocioso"|"adequado"|"sobrecarregado",
             "folga_ua": float, "mensagem": str}
    """


def sobrepostos(piquetes: list[dict]) -> list[dict]:
    """Pares de piquetes cujos polígonos se cruzam.

    `piquetes`: [{"id": str, "anel": [(lon, lat), ...]}, ...]

    Retorna [{"a": str, "b": str, "area_sobreposta_ha": float,
              "pct_do_menor": float}, ...], do maior ao menor.
    """
```

**Assine exatamente assim.**

## ⛔ O defeito da primeira tentativa (2026-08-05)

A entrega anterior passou nos seis critérios de aceite e **ainda assim estava errada**.
O defeito não estava coberto por nenhum teste, e é este:

> **`sobrepostos()` projetou cada polígono na zona UTM do próprio centro e depois
> comparou as geometrias entre si.**

`services/geometria._poligono_projetado` escolhe o CRS a partir do centro do polígono que
recebe. Dois piquetes em zonas UTM diferentes voltam em **referenciais diferentes** — e
comparar metros medidos a partir de origens distintas não significa nada. Reprodução:

```
A em lon -55 (zona 21, EPSG:32721) -> centro métrico (693.388, 6.678.968)
B em lon -49 (zona 22, EPSG:32722) -> centro métrico (693.388, 6.678.968)

sobrepostos([A, B]) -> [{'a':'A','b':'B','area_sobreposta_ha':106.97,'pct_do_menor':100.0}]
distância real entre A e B: ~578 km
```

**100 % de sobreposição entre dois piquetes a 578 km um do outro.**

### Por que isso importa mesmo sendo raro

Numa fazenda só, todos os piquetes caem na mesma zona e o defeito nunca aparece. Mas:

1. As zonas UTM têm 6° de largura e **várias fazendas brasileiras ficam em cima de uma
   divisa** — em -54° e -48° há divisa, e isso corta MS, MT, RS e PA.
2. Desde a etapa B4 o sistema é **multi-propriedade** (§3). Comparar piquetes de
   propriedades diferentes da mesma organização é caso de uso previsto, e propriedades em
   estados diferentes caem em zonas diferentes.

E o modo de falha é o pior possível: **silencioso e plausível**. Não estoura, não avisa —
devolve um número com quatro casas decimais que parece resultado de cálculo.

### O que a nova entrega precisa fazer

**Projete todos os polígonos num único CRS**, escolhido uma vez para o conjunto — o do
centro do primeiro polígono válido, ou o do centro de todos. Diga na docstring qual
critério usou e por quê.

Se dois polígonos estiverem longe demais para um CRS comum fazer sentido (por exemplo,
mais de uma zona de distância), **não os compare** e registre isso no retorno. Devolver
"sem sobreposição" seria a resposta certa pela razão errada, e a próxima pessoa não teria
como saber a diferença.

### Teste obrigatório

Além dos seis critérios originais, a entrega **só é aceita** com um teste que reproduza o
caso acima — dois quadrados na mesma latitude, em zonas UTM diferentes, à mesma distância
do meridiano central de cada uma — e comprove que **não** são reportados como sobrepostos.
Sem esse teste, o defeito volta na próxima refatoração.

## Regras que decidem a correção

**Lotação usa peso real, não cabeças.** Vinte bezerros de 200 kg não pesam o mesmo que
vinte bois de 500. Contar cabeça é o erro que faz o pecuarista superlotar sem perceber.

**A faixa de `situacao` precisa de tolerância.** Lotação exatamente igual ao alvo é
`adequado`; use ±10 % antes de chamar de ocioso ou sobrecarregado. Um piquete a 1,01 UA/ha
com alvo de 1,00 não está sobrecarregado — está adequado, e alertar isso vira ruído.

**Sobreposição mínima não é sobreposição.** Polígonos desenhados à mão quase sempre se
tocam nas bordas por alguns metros. **Ignore sobreposições abaixo de 1 % da área do menor
piquete** — e diga isso na docstring, porque é decisão, não detalhe.

## Critério de aceite

1. Dez animais de 450 kg em 10 ha dão exatamente `ua_por_ha = 1.0`.
2. `avaliar_lotacao` com atual igual ao alvo devolve `adequado`, e 1 % acima também.
3. Dois quadrados idênticos são detectados com `pct_do_menor` próximo de 100.
4. Dois quadrados que só encostam na borda **não** aparecem na lista.
5. Área zero e lista vazia não estouram nem dividem por zero.
6. Polígono inválido é **pulado com registro**, não derruba a checagem dos demais — um
   piquete mal desenhado não pode impedir a conferência da fazenda inteira.

## Proibições

- ❌ Não toque em `app.py`, `database.py`, `repositories/`, `ui/`, nem em módulo existente
  de `services/`.
- ❌ **Não reimplemente área nem projeção** — importe de `services/geometria.py` (R8).
  Mas **escolher o CRS do conjunto é decisão desta spec**, não de `geometria.py`: aquele
  módulo trata um polígono por vez e está correto assim. Se precisar de uma função pública
  para projetar num CRS dado, **proponha no PR** — a tentativa anterior importou o
  `_poligono_projetado` privado, e depender de um `_` de outro módulo quebra na primeira
  refatoração.
- ❌ Não consulte banco.
- ❌ Não crie tabela nem migration.
- ❌ **Não estime capacidade por tipo de pasto.** Exige dado agronômico que o sistema não
  tem; `ua_por_ha_alvo` entra por parâmetro.

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t .
git diff --stat origin/main
```

## Entrega

PR para `main`. No corpo, mostre o caso dos dois piquetes que só encostam na borda e **não**
são reportados — é o que separa a função útil da que gera alarme falso.
