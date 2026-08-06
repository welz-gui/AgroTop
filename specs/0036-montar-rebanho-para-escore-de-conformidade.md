# Spec 0036 — Montar o dict `rebanho` que `services/conformidade.py` espera

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 1-2 dias
- **Branch:** `feat/montar-rebanho-conformidade`
- **Crie:** `services/conformidade_adaptador.py` e
  `tests/test_conformidade_adaptador.py` — **arquivos novos**

---

## Regra de ouro desta spec

Você cria **um arquivo novo**. **Não altere `services/conformidade.py`** — ele acabou de
sair de um retrabalho (spec 0029 → PR #95) e está correto e testado. O problema aqui é só
a entrada.

## Contexto

`services/conformidade.avaliar(rebanho: dict, referencia: str)` calcula o escore de
conformidade do §PNIB inteiro a partir de **contagens já prontas**:

```python
{
    "animais_ativos": int,
    "com_identificacao_oficial": int,
    "com_identificacao_manejo": int,
    "com_propriedade": int,
    "nascidos_sem_mae": int,
    "eventos_pendentes_sincronizacao": int,
    "com_nascimento_estimado": int,
    "dispositivos_com_divergencia": int,
    "movimentacoes_abertas_vencidas": int,
}
```

Nenhum lugar do sistema produz esse dict hoje. As contagens existem espalhadas — em
`animal_identifiers`, `animals.propriedade_nascimento_id`/`property_id`, `partos`,
`animal_events`/`evento_sincronizacao`, `dispositivos`, `movimentacoes` — mas cada uma com
sua própria forma de "conta isso".

## Objetivo

Uma função pura que recebe as listas cruas dessas fontes (já buscadas por quem chamar) e
devolve o dict de contagens pronto para `conformidade.avaliar()`.

## Contrato obrigatório

```python
def montar_rebanho(
    *,
    animais: list[dict],
    # cada um: {"uuid": str, "status": str, "property_id": str|None,
    #           "propriedade_nascimento_id": str|None, "origem": str,
    #           "birth_estimated": bool, "mae_uuid": str|None}
    identificadores_ativos: list[dict],
    # cada um: {"animal_uuid": str, "tipo": str}  -- tipo é um de
    # services.identificadores.TIPOS (confira o módulo antes de supor os valores)
    dispositivos: list[dict],
    # cada um: {"animal_uuid": str|None, "divergencia": str|None}
    eventos_pendentes: int,
    # já é a contagem — vem pronta de `repositories.eventos.contar_pendentes()`,
    # que já existe e já faz essa conta corretamente. Não recalcule.
    movimentacoes_abertas: list[dict],
    # cada um: {"status": str, "data_prevista": str}
    referencia: str,   # "AAAA-MM-DD" — mesma data passada a conformidade.avaliar()
) -> dict:
    """Ver services/conformidade.py para o formato de saída exato."""
```

## Regras que decidem a correção

**"Animal ativo" é o universo, e só ele entra na contagem.** `animais_ativos` é
`len([a for a in animais if a["status"] == "ativo"])`, e **todas as outras contagens
também são só sobre esse subconjunto** — um identificador oficial de um animal vendido
não conta para "quantos ativos têm identificação oficial". Errar isso deixaria o escore
mentir para os dois lados.

**"Com propriedade" olha `property_id`, não `propriedade_nascimento_id`.** São campos
diferentes por razão diferente: o segundo é histórico (§7, onde nasceu), o primeiro é
atual (§3, onde está agora). O §3 do escore pergunta "onde ele está", não "onde nasceu".

**"Nascidos sem mãe" só conta quem `origem == "nascido"`.** Um animal comprado
legitimamente não tem `mae_uuid` e isso não é pendência nenhuma — a spec 0029 já cobre
esse raciocínio na dimensão do §7; não repita o erro de contar todo `mae_uuid is None`.

**"Movimentação aberta vencida"** é `status` em `("rascunho", "liberada",
"em_transito")` **e** `data_prevista` anterior a `referencia`. As duas condições, não
uma. Uma movimentação aberta com data futura não é vencida, é normal.

**Identificador "de manejo" e "oficial" contam separado**, cada um filtrando por `tipo`
— não invente um terceiro critério combinado.

## Critério de aceite

1. Animal inativo (vendido/morto) nunca aparece em nenhuma contagem, mesmo que tenha
   identificação oficial, dispositivo com divergência, etc.
2. Animal comprado (`origem != "nascido"`) sem `mae_uuid` **não** conta como "nascido sem
   mãe".
3. Movimentação com `status="liberada"` e `data_prevista` de ontem conta como vencida;
   a mesma com `data_prevista` de amanhã não conta.
4. `eventos_pendentes_sincronizacao` no resultado é exatamente o inteiro recebido — a
   função não recalcula, só repassa.
5. Rebanho vazio (`animais=[]`) devolve todas as contagens em 0, sem estourar.
6. O resultado, passado direto para `conformidade.avaliar(resultado, referencia)`, produz
   um escore sem lançar exceção para pelo menos três cenários: rebanho perfeito, rebanho
   com pendências em todas as dimensões, rebanho vazio.

## Proibições

- ❌ Não altere `services/conformidade.py`.
- ❌ Não consulte banco — as listas chegam prontas.
- ❌ Não invente uma dimensão nova além das nove contagens do contrato.
- ❌ Não toque em `database.py`, `repositories/`, `app.py`.

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t .
git diff --stat origin/main
```

## Entrega

PR para `main`. No corpo, um rebanho fictício de uns 10 animais com pendências variadas,
a saída de `montar_rebanho()` sobre ele, e o escore final de `conformidade.avaliar()`.
