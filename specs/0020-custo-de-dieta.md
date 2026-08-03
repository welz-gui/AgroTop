# Spec 0020 — Custo de dieta multi-ingrediente (função pura)

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 1–2 dias
- **Branch:** `feat/custo-dieta`
- **Crie:** `services/dieta.py` e `tests/test_dieta.py` — **arquivos novos**

---

## Regra de ouro desta spec

Você cria **arquivos novos**. **Não altere nenhum arquivo existente.** Seu produto é uma
função pura, testada, com contrato fixo — o mantenedor liga à interface e ao banco depois
(ROADMAP R31).

## Objetivo

A dieta é o **maior custo variável** do confinamento, e hoje o sistema não sabe quanto custa
alimentar um animal por dia. Sem isso não existe custo por arroba produzida — e sem esse
número a Trilha 3 inteira não fecha.

## Contrato obrigatório

```python
def custo_por_cabeca_dia(ingredientes: list[dict]) -> dict:
    """Custo diário de uma dieta, por cabeça.

    `ingredientes`: [{
        "insumo_id": int, "nome": str,
        "quantidade_kg_cabeca_dia": float,
        "custo_por_kg": float,
        "materia_seca_pct": float,   # 0..100
    }, ...]

    Retorna:
        {
          "custo_dia": float,            # R$ por cabeça/dia
          "kg_materia_natural": float,
          "kg_materia_seca": float,
          "participacao": [{"nome": str, "pct_custo": float}, ...],
        }
    """


def custo_por_arroba_produzida(custo_dia: float, gmd: float,
                               rendimento_carcaca: float) -> float | None:
    """Quanto custa produzir uma arroba nessa dieta. `None` se GMD <= 0."""
```

**Assine exatamente assim.** Use `services.constantes.KG_PER_ARROBA` — não reimplemente (R8).

## O que separa este cálculo de uma soma

**Matéria natural não é matéria seca.** Silagem com 30 % de MS e milho com 88 % não se somam
como se fossem a mesma coisa: 10 kg de silagem entregam 3 kg de MS. Confundir as duas
superestima a dieta em várias vezes — é o erro clássico da área, e o motivo de a função
devolver os dois números separados.

`participacao` existe para responder **qual ingrediente domina o custo**, que quase nunca é
o que domina o peso.

## Critério de aceite

1. Dieta com 10 kg de silagem a 30 % de MS devolve `kg_materia_seca = 3.0`.
2. `participacao` soma 100 % (com tolerância de arredondamento) e vem ordenada do maior.
3. `custo_por_arroba_produzida` com GMD zero ou negativo devolve `None` — **não** zero nem
   infinito. Dieta que não engorda não tem custo por arroba, e zero mentiria.
4. Lista vazia devolve zeros sem estourar.
5. `materia_seca_pct` fora de 0..100 é recusado com mensagem clara.

## Proibições

- ❌ Não toque em `app.py`, `database.py`, `repositories/`, `ui/`, nem em módulo existente
  de `services/`.
- ❌ **Não consulte banco.** Tudo entra por parâmetro.
- ❌ Não crie tabela nem migration (R4: schema é do mantenedor).
- ❌ Não integre à interface.
- ❌ **Não invente tabela nutricional.** Se faltar dado de composição, ele entra por
  parâmetro — estimar valor de MS por tipo de alimento produz número que parece autoridade
  e não é.

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t .
git diff --stat origin/main
```

O `-t .` não é opcional (R16) e o `AGROTOP_FORCE_SQLITE=1` é a segunda trava.

## Entrega

PR para `main`, pronto para revisão. No corpo, mostre uma dieta em que o ingrediente de
**maior peso não é o de maior custo** — é o caso que justifica `participacao` existir.
