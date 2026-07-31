# Spec 0012 — Máquina de estados do animal (função pura)

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 1–2 dias
- **Branch:** `feat/estados-animal`
- **Crie:** `services/estados_animal.py` e `tests/test_estados_animal.py` — **arquivos novos**
- **Base regulatória:** [PNIB §4.4](../docs/regulatorio/requisitos_sistema_pnib_rs.md)

---

## Regra de ouro

Você cria **arquivos novos**. **Não altere nenhum arquivo existente** — em especial
`database.py`, que está em migração estrutural. Seu produto é uma função pura, testada,
com contrato fixo. O mantenedor liga ao banco depois.

## A pergunta que esta função responde

**Esta transição de estado é permitida? Se não for, por quê — e o que seria preciso para
permiti-la?**

Hoje o animal tem 4 estados de fato (`ativo`, `carencia`, `vendido`, `morto`) e **nenhuma
regra de transição**: um `UPDATE` pode levar de qualquer estado a qualquer outro. O PNIB
(§4.4) exige estados com regras, e é explícito:

> *"Um animal morto ou abatido não pode retornar ao estado ativo sem procedimento
> administrativo autorizado e auditado."*

## Contrato obrigatório

```python
def transicao_permitida(
    estado_atual: str,
    estado_novo: str,
    *,
    tem_autorizacao: bool = False,
) -> dict:
    """Avalia se a mudança de estado do animal é permitida.

    `tem_autorizacao`: o usuário possui a permissão específica exigida para
    transições sensíveis (§14.2). Injetado — a função não consulta permissões.

    Retorna:
        {
          "permitida": bool,
          "exige_autorizacao": bool,   # True se só passa com autorização
          "exige_justificativa": bool,
          "motivo": str,               # vazio quando permitida sem ressalva
        }
    """


def estados() -> list[str]:
    """Lista dos estados válidos, na ordem em que devem aparecer na interface."""


def estados_finais() -> set[str]:
    """Estados dos quais só se sai com autorização (morto, abatido, vendido…)."""
```

**Assine exatamente assim.**

## Estados a suportar

Comece por estes, do §4.4 — os quatro primeiros já existem hoje:

`ativo` · `carencia` · `vendido` · `morto` · `rascunho` ·
`ativo_sem_identificacao_oficial` · `identificado_oficialmente` ·
`identificacao_pendente_sincronizacao` · `identificacao_rejeitada` ·
`movimentacao_programada` · `em_transito` · `transferido` · `abatido` ·
`desaparecido` · `furtado` · `baixado_por_ajuste` · `cadastro_bloqueado`

Estruture para que **acrescentar estado seja trivial** — uma tabela de transições, não uma
cadeia de `if`.

## Regras mínimas

| Situação | Resultado |
|---|---|
| `morto` → `ativo` | permitida **somente com autorização** + justificativa |
| `abatido` → qualquer ativo | idem |
| `vendido` → `ativo` | idem (estorno de venda) |
| `ativo` → `carencia` | livre |
| `carencia` → `ativo` | livre |
| `rascunho` → `ativo` | livre |
| qualquer → `rascunho` | **nunca** — rascunho é estado inicial |
| estado igual ao atual | permitida, sem efeito |
| estado inexistente | **não permitida**, com motivo claro |

As mensagens de `motivo` serão lidas por um operador. Escreva em português, dizendo **o que
falta**: `"Animal morto só volta a ativo com autorização de administrador e justificativa
registrada."`

## Testes obrigatórios

Cada transição da tabela nos dois sentidos (com e sem autorização), estado inválido, estado
igual ao atual, e a lista de estados finais.

## Critério de aceite

1. Contrato respeitado exatamente.
2. Toda transição sensível exige autorização **e** justificativa.
3. Adicionar um estado novo não exige tocar na lógica — só na tabela de transições.
4. `services/estados_animal.py` não importa `streamlit`, `database` nem driver de banco (R9).
5. Suíte verde.

## Proibições

- ❌ Não altere arquivo existente, nem os estados usados hoje em `database.py`.
- ❌ Não consulte o banco nem verifique permissões — `tem_autorizacao` é injetado.
- ❌ Não crie migration nem toque no schema (R4).
- ❌ Não adicione dependência.

## Verificação antes do PR

```bash
python -m unittest discover -s tests -t . -v
git diff --stat origin/main    # apenas os 2 arquivos novos
```
