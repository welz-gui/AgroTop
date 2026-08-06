# Spec 0038 — Montar o contexto que `services/gta.py` precisa para validar

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 1-2 dias
- **Branch:** `feat/montar-contexto-gta`
- **Crie:** `services/gta_adaptador.py` e `tests/test_gta_adaptador.py` —
  **arquivos novos**

---

## Regra de ouro desta spec

Você cria **um arquivo novo**. **Não altere `services/gta.py`.**

## ⚠️ Leia isto antes de começar: parte do dado ainda não existe no banco

`services/gta.py::validar(gta, contexto)` valida o **documento físico da GTA** — emissão,
validade, quantidade de animais declarada, UF de origem/destino. A tabela `movimentacoes`
(criada na etapa B6) guarda `gta_numero`, mas **não guarda `emissao`, `validade` nem
`quantidade` declarada no papel** — esses campos não existem no schema hoje.

Isso não bloqueia esta spec. O contrato abaixo recebe esses campos **como parâmetro**,
como se já tivessem sido digitados em algum lugar (a decisão de onde coletá-los —
formulário novo, campo novo em `movimentacoes` — é do mantenedor, depois). Sua função
só faz a ponte entre "dados que existem hoje" (movimentação, animais, dispositivos) e
"dados que o §8 do papel exige" (que podem vir prontos ou não).

## Objetivo

Uma função pura que monta os dicts `gta` e `contexto` que `services/gta.validar()`
espera, a partir de uma movimentação real e do estado do rebanho.

## Contrato obrigatório

```python
def montar_contexto(
    movimentacao: dict,
    # {"gta_numero": str, "propriedade_origem_nome": str, "propriedade_destino_nome": str,
    #  "finalidade": str, "animais_uuids": list[str]}  -- já existe hoje
    dados_do_documento: dict,
    # {"emissao": "AAAA-MM-DD"|None, "validade": "AAAA-MM-DD"|None,
    #  "quantidade_declarada": int|None}  -- ainda não persistido; ver aviso acima
    animais_no_embarque_uuids: list[str],
    # quem fisicamente subiu no caminhão — pode divergir da lista da movimentação
    animais_em_carencia_uuids: list[str],
    hoje: str,
) -> tuple[dict, dict]:
    """Retorna (gta, contexto) prontos para services.gta.validar(gta, contexto).

    `gta["animais"]` usa os UUIDs da movimentação (não os brincos — §4.1: a identidade
    é o uuid). `contexto["animais_no_embarque"]` e `contexto["animais_em_carencia"]`
    usam o mesmo espaço de identificadores, senão a comparação de conjuntos que
    `gta.validar` faz por dentro (animal no embarque × animal na GTA) nunca bate.
    """
```

## Regras que decidem a correção

**Campo ausente em `dados_do_documento` vira campo ausente em `gta`, não um valor
inventado.** `services/gta.validar` já sabe pular verificações quando a chave falta do
contexto — é assim que o módulo foi desenhado (releia o docstring de `validar`). Preencher
com um valor "razoável" por engano faria o validador rodar uma checagem que não devia,
com um dado que não existe de verdade.

**`uf_origem`/`uf_destino` não vêm de lugar nenhum ainda** — `movimentacoes` guarda nome
de propriedade, não UF. Deixe esses dois campos de fora do `gta` retornado (ausentes, não
`None` — mesma regra do parágrafo acima) e documente isso no docstring da função. Não
tente extrair UF do nome da propriedade por heurística.

**`quantidade` só entra em `gta` se `dados_do_documento["quantidade_declarada"]` não for
`None`.** Repare que `gta.validar` compara `quantidade` contra `len(animais)` — se você
sempre preencher `quantidade = len(movimentacao["animais_uuids"])` por padrão, a
checagem `quantidade_divergente` nunca dispara, porque estaria sempre comparando o
mesmo número consigo mesmo. Isso destruiria o propósito da checagem.

## Critério de aceite

1. `dados_do_documento` completo (emissão, validade, quantidade) produz um `gta` com
   todos os campos, e `gta.validar()` sobre ele roda todas as checagens.
2. `dados_do_documento` com tudo `None` produz um `gta` sem esses três campos, e
   `gta.validar()` não levanta as checagens `gta_vencida`, `gta_futura`,
   `validade_maior_que_o_permitido` nem `quantidade_divergente` (que dependem deles) —
   comportamento que já vem de `gta.py`; o teste aqui prova que o adaptador não
   introduz valor falso que force essas checagens a rodar.
3. `animais_no_embarque_uuids` diferente de `movimentacao["animais_uuids"]` gera, ao
   final, pelo menos um problema `animal_no_embarque_fora_da_gta` ou
   `animal_da_gta_ausente` quando passado por `gta.validar()`.
4. `uf_origem`/`uf_destino` nunca aparecem no `gta` retornado — confirme com
   `"uf_origem" not in gta`.
5. Lista de UUIDs vazia em qualquer um dos três parâmetros de animais não estoura.

## Proibições

- ❌ Não altere `services/gta.py`.
- ❌ Não proponha nem implemente as colunas que faltam em `movimentacoes` — schema é
  fora do escopo desta spec.
- ❌ Não invente UF a partir do nome da propriedade.
- ❌ Não consulte banco.
- ❌ Não toque em `database.py`, `repositories/`, `app.py`.

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t .
git diff --stat origin/main
```

## Entrega

PR para `main`. No corpo, dois exemplos: um com `dados_do_documento` completo (mostrando
`gta.validar()` encontrando um problema de verdade, como GTA vencida) e um com tudo
ausente (mostrando que nada quebra e nada é inventado).
