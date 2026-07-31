# Spec 0011 — Motor de regras de recomendação (função pura)

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 2–3 dias
- **Branch:** `feat/motor-de-regras`
- **Crie:** `services/recomendacoes.py` e `tests/test_recomendacoes.py` — **arquivos novos**

---

## Regra de ouro desta spec

Você cria **arquivos novos**. **Não altere nenhum arquivo existente.** O mantenedor liga à
interface depois.

## Objetivo, e por que ele não é "IA"

Regras explícitas, com motivo e dados à vista. **Isto não é machine learning e não deve
tentar ser** — modelos estatísticos dependem de dados que o projeto ainda não tem (ver
[spec 0006](0006-poc-dados-modelos-preditivos.md)).

O motor de regras entrega valor agora **e** força a definir exatamente as features que um
modelo usaria depois. É engenharia de features feita antes da hora — não prêmio de
consolação ([ROADMAP.md](../ROADMAP.md), Trilha 4).

## Contrato obrigatório

```python
def avaliar(contexto: dict) -> list[dict]:
    """Aplica as regras ao estado da fazenda e devolve recomendações.

    `contexto` traz os dados já apurados — a função NÃO consulta o banco:
        {
          "animais": [{"id", "peso", "peso_alvo", "gmd", "lote_id",
                       "carencia_ate": "AAAA-MM-DD"|None}, ...],
          "lotes":   [{"id", "capacidade_ua", "ua_atual"}, ...],
          "insumos": [{"id", "nome", "saldo", "consumo_diario"}, ...],
          "preco_arroba": float|None,
          "custo_por_arroba": float|None,
          "hoje": "AAAA-MM-DD",
        }

    Retorna:
        [{
          "regra": str,            # identificador estável, ex. "estoque_insuficiente"
          "severidade": "alta"|"media"|"baixa",
          "titulo": str,           # uma linha
          "motivo": str,           # POR QUE disparou, com os números
          "dados": dict,           # valores que sustentam a conclusão
          "acao": str,             # o que fazer
        }, ...]

    Chave ausente no contexto NÃO pode quebrar: a regra que depende dela é pulada.
    """
```

**Assine exatamente assim.** Toda recomendação **precisa** trazer `motivo` e `dados` — é
requisito registrado no ROADMAP: recomendação sem explicação não é aceita.

## Regras a implementar

| regra | Dispara quando | Severidade |
|---|---|---|
| `estoque_insuficiente` | saldo do insumo < consumo previsto de 15 dias | alta |
| `piquete_acima_da_capacidade` | `ua_atual` > `capacidade_ua` | alta |
| `carencia_impede_abate` | animal pronto para abate, mas em carência | alta |
| `pronto_para_venda` | peso ≥ peso-alvo e sem carência | média |
| `gmd_abaixo_da_meta` | GMD do animal < meta (padrão 0,5 kg/dia) | média |
| `margem_em_risco` | `custo_por_arroba` > `preco_arroba` | alta |

Comece por estas seis. Estrutura o código para que **acrescentar regra seja trivial** —
uma lista de funções, cada uma recebendo o contexto e devolvendo zero ou mais
recomendações.

## Qualidade das mensagens

São lidas por um pecuarista, não por um programador. Compare:

- ❌ `"threshold exceeded: ua_atual=32.5 > capacidade_ua=28.0"`
- ✅ **título:** `"Piquete P3 acima da capacidade"`
  **motivo:** `"32,5 UA em um piquete com capacidade para 28,0 UA (16% acima)."`
  **acao:** `"Mover animais para outro piquete ou antecipar a venda dos mais pesados."`

## Testes obrigatórios

`tests/test_recomendacoes.py`: cada regra disparando, cada regra **não** disparando,
contexto vazio (lista vazia, sem erro), contexto com chaves faltando (regras dependentes
puladas, demais funcionando), e várias regras disparando juntas.

## Critério de aceite

1. Contrato respeitado exatamente.
2. As seis regras implementadas e testadas nos dois sentidos.
3. Toda recomendação traz `motivo` e `dados` preenchidos — **teste isso explicitamente**.
4. Contexto incompleto não quebra.
5. `services/recomendacoes.py` não importa `streamlit`, `database` nem driver de banco (R9).
6. Suíte verde.

## Proibições

- ❌ Não altere arquivo existente.
- ❌ Não consulte o banco: tudo vem do `contexto`.
- ❌ **Não use machine learning, nem biblioteca de ML.** Regra explícita, sempre.
- ❌ Não reimplemente cálculo que já existe em `services/` (R8). Se precisar de arroba ou
  categoria de idade, o contexto deve trazer pronto — ajuste o contexto, não duplique regra.
- ❌ Não adicione dependência.

## Como verificar antes de abrir o PR

```bash
python -m unittest discover -s tests -t . -v
git diff --stat origin/main    # apenas os 2 arquivos novos
```

## Entrega

PR para `main` com um exemplo de saída completa para um contexto realista — mostrando
título, motivo, dados e ação de pelo menos três regras.
