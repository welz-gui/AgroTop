# Spec 0028 — Lotação e sobreposição de piquetes (função pura)

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 1–2 dias
- **Branch:** `feat/geometria-lotacao`
- **Crie:** `services/lotacao.py` e `tests/test_lotacao.py` — **arquivos novos**

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
