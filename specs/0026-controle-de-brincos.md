# Spec 0026 — 🇧🇷 Controle de estoque de brincos (PNIB §5)

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 1–2 dias
- **Branch:** `feat/controle-de-brincos`
- **Crie:** `services/dispositivos.py` e `tests/test_dispositivos.py` — **arquivos novos**

---

## Regra de ouro desta spec

Você cria **arquivos novos**. **Não altere nenhum arquivo existente.**

## Objetivo

A etapa **B7** vai implementar o módulo de dispositivos. Esta spec entrega a **regra pura**
que ela precisa.

Brinco oficial vem em **faixas numéricas** compradas do órgão. O §5 exige saber, de cada
número: se foi aplicado, em qual animal, se foi perdido, danificado ou inutilizado. Aplicar
um número que já está em outro animal, ou fora da faixa que a propriedade possui, gera
inconsistência que só aparece na fiscalização.

## Contrato obrigatório

```python
def expandir_faixa(inicio: str, fim: str) -> list[str]:
    """Todos os números de uma faixa, inclusive nas pontas.

    Os identificadores têm prefixo alfanumérico e sufixo numérico
    ("BR0001".."BR0100"). O prefixo tem de ser idêntico nas duas pontas.
    Levanta ValueError se o prefixo divergir ou se `fim` < `inicio`.
    """


def validar_aplicacao(numero: str, faixas: list[dict],
                      aplicados: dict) -> dict:
    """Este número pode ser aplicado agora?

    `faixas`: [{"inicio": str, "fim": str, "status": "disponivel"|"cancelada"}, ...]
    `aplicados`: {numero: {"animal_uuid": str, "status": "ativo"|"removido"}}

    Retorna {"pode": bool, "motivo": str, "codigo": str}
    """


def situacao_do_estoque(faixas: list[dict], aplicados: dict) -> dict:
    """Quantos brincos restam.

    Retorna {"total": int, "aplicados": int, "disponiveis": int,
             "percentual_usado": float,
             "proximos_disponiveis": [str, ...]}   # até 10
    """
```

**Assine exatamente assim.**

## Regras de `validar_aplicacao`

| código | Quando | `pode` |
|---|---|---|
| `fora_das_faixas` | número não pertence a nenhuma faixa da propriedade | False |
| `faixa_cancelada` | pertence a uma faixa com status `cancelada` | False |
| `ja_aplicado_ativo` | já está ativo em outro animal | False |
| `reaproveitavel` | esteve aplicado, mas está `removido` | **True** |
| `disponivel` | dentro da faixa e nunca aplicado | True |

**`reaproveitavel` permite a aplicação**, e é uma decisão do §4.2 já implementada em
`repositories/identificadores.py`: brinco de animal baixado pode voltar a ser usado, desde
que o histórico mostre quem o usou antes. Recusar aqui contradiria o resto do sistema.

## Critério de aceite

1. `expandir_faixa("BR0001", "BR0010")` devolve 10 números, com o zero à esquerda preservado.
2. Prefixos diferentes levantam `ValueError` — `expandir_faixa("BR0001", "MT0010")`.
3. Faixa invertida (`fim` < `inicio`) levanta `ValueError`.
4. Cada código da tabela tem teste que o dispara.
5. `situacao_do_estoque` com faixas grandes (100 mil números) **não estoura memória nem
   demora** — pense antes de materializar a lista inteira. Diga no PR como resolveu.
6. `proximos_disponiveis` respeita a ordem numérica, não a alfabética: `BR0009` vem antes de
   `BR0010`.

## Proibições

- ❌ Não toque em `app.py`, `database.py`, `repositories/`, `ui/`, nem em módulo existente
  de `services/`.
- ❌ **Não consulte banco.** Tudo entra por parâmetro.
- ❌ Não crie tabela nem migration (a B7 é do mantenedor, R4).
- ❌ **Não valide o formato do número oficial do PNIB.** O formato ainda não foi publicado
  (§23) — `services/identificadores.py` já trata isso como configurável, e inventar máscara
  aqui contradiria aquela decisão.

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t .
git diff --stat origin/main
```

## Entrega

PR para `main`, pronto para revisão. No corpo, diga como resolveu a faixa de 100 mil números
sem materializá-la.
