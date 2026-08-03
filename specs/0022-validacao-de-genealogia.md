# Spec 0022 — 🇧🇷 Validação de vínculo materno (PNIB §7)

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 1 dia
- **Branch:** `feat/validacao-genealogia`
- **Crie:** `services/genealogia.py` e `tests/test_genealogia.py` — **arquivos novos**

---

## Regra de ouro desta spec

Você cria **arquivos novos**. **Não altere nenhum arquivo existente.**

## Objetivo

A etapa **B3** da Fase B vai introduzir genealogia no schema. Esta spec entrega a **regra
pura** que ela vai precisar, para que a migração e a regra avancem em paralelo — o mesmo
arranjo que funcionou nas specs 0012, 0013 e 0014.

O §7 do PNIB exige vínculo materno no nascimento. Vínculo errado **propaga**: a cria herda a
rastreabilidade de outro animal, e o erro só aparece anos depois, numa auditoria.

## Contrato obrigatório

```python
def validar_vinculo(cria: dict, mae: dict | None,
                    contexto: dict | None = None) -> list[dict]:
    """Problemas no vínculo materno. Lista vazia = consistente.

    `cria`: {"id", "sexo", "nascimento", "propriedade_id"}
    `mae`:  {"id", "sexo", "nascimento", "propriedade_id", "morte"} | None
    `contexto`: {
        "hoje": "AAAA-MM-DD",
        "idade_minima_parto_meses": int,       # padrão 18
        "intervalo_minimo_partos_dias": int,   # padrão 270
        "partos_anteriores": ["AAAA-MM-DD", ...],
    }

    Retorna [{"codigo": str, "gravidade": "bloqueio"|"alerta"|"informativo",
              "mensagem": str, "campo": str | None}, ...]
    """
```

**Assine exatamente assim.** Chave ausente no contexto faz a validação correspondente ser
**pulada**, não falhar — mesmo contrato de `services/validacao_regulatoria.py`.

## Validações obrigatórias

| código | Quando | Gravidade |
|---|---|---|
| `mae_macho` | `mae["sexo"]` não é fêmea | bloqueio |
| `mae_mais_nova_que_cria` | nascimento da mãe ≥ nascimento da cria | bloqueio |
| `mae_jovem_demais` | mãe com menos de `idade_minima_parto_meses` na data do parto | bloqueio |
| `parto_apos_morte_da_mae` | nascimento da cria depois da morte da mãe | bloqueio |
| `intervalo_entre_partos_curto` | menos de `intervalo_minimo_partos_dias` do parto anterior | alerta |
| `mae_em_outra_propriedade` | `propriedade_id` diferente na data do parto | alerta |
| `sem_mae_vinculada` | `mae` é `None` | informativo |

**`intervalo_entre_partos_curto` é alerta, não bloqueio.** Biologicamente improvável não é
impossível — pode ser data digitada errada, pode ser parto real. Bloquear o cadastro por
isso trava o usuário sem prova, e o §7 não exige.

**`mae_em_outra_propriedade` também é alerta**: transferência no fim da gestação acontece, e
a data exata do parto nem sempre é conhecida.

## Critério de aceite

1. Cada código acima tem **um teste que o dispara e um que não** — regra sem o segundo
   teste passa acusando tudo.
2. Vaca de 24 meses parindo passa; de 12 meses é bloqueada.
3. Contexto vazio não estoura: só as validações possíveis rodam, e o teste mostra quais.
4. Mensagens em português, citando as datas que motivaram — "mãe jovem demais" sem dizer a
   idade não ajuda ninguém a corrigir.

## Proibições

- ❌ Não toque em `app.py`, `database.py`, `repositories/`, `ui/`, nem em módulo existente
  de `services/`.
- ❌ **Não consulte banco.** Tudo entra por parâmetro.
- ❌ Não crie tabela nem migration — a genealogia entra no schema pela etapa B3, que é do
  mantenedor (R4).
- ❌ Não integre à interface.
- ❌ **Não valide consanguinidade.** Exige a árvore inteira e não está no escopo do §7.

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t .
git diff --stat origin/main
```

## Entrega

PR para `main`, pronto para revisão. No corpo, liste **quais validações foram puladas com
contexto vazio** e por quê — é o comportamento que o integrador precisa conhecer.
