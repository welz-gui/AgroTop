# Spec 0032 — 🇧🇷 Mapa de conformidade: cada exigência do PNIB e onde ela está

- **Tipo:** documentação verificável · **Risco:** baixo · **Esforço:** 2 dias
- **Branch:** `feat/mapa-de-conformidade-v2` — a `feat/mapa-de-conformidade` continua no
  remoto, ligada à PR fechada, e **não** deve ser reaproveitada.
- **Estado:** 🔁 **retrabalho** — a [PR #89](https://github.com/welz-gui/AgroTop/pull/89)
  foi fechada com defeito confirmado. Leia **"O defeito da primeira tentativa"** antes de
  começar.
- **Crie:** `docs/regulatorio/mapa-de-conformidade.md` e
  `tests/test_mapa_conformidade.py`

---

## Regra de ouro desta spec

Você cria **arquivos novos**. **Não altere código de produção.** Se encontrar exigência não
atendida, **registre no mapa** — não implemente.

## Objetivo

O projeto passou por sete etapas de conformidade (B1 a B7) e ninguém consegue responder,
sem reler tudo: **quais exigências do PNIB estão atendidas, quais não, e onde cada uma
mora no código.**

Isso importa por dois motivos:

1. **Auditoria.** Se o órgão perguntar "onde vocês registram o vínculo materno?", a
   resposta precisa ser um arquivo e uma linha, não uma investigação.
2. **Honestidade interna.** Sem o mapa, é fácil acreditar que o sistema atende mais do que
   atende — e essa crença é perigosa num sistema com valor regulatório.

## ⛔ O defeito da primeira tentativa (2026-08-05)

A entrega anterior tinha estrutura correta, contagem consistente (13+10+1+1+1 = 26) e os
quatro testes passando. E cometeu **exatamente o erro que esta spec nomeia como o mais
grave que o documento pode conter**:

> | §6 | Histórico de eventos e imutabilidade auditável do animal | ✅ atendido | Onde:
> `database.py` (`init_db`), `repositories/movimentacoes.py` (`criar`),
> `repositories/nascimentos.py` (`registrar`), `repositories/pesagens.py` (`add_weighing`). |

**§6 não tem interface.** Os eventos são gravados em toda operação desde a etapa B2, mas
não existe nenhuma tela que os mostre — `repositories/eventos.py` tem **zero leitura** em
`app.py`. A única ocorrência da palavra `eventos` naquele arquivo é uma variável local.

Repare que a própria linha denuncia o problema: **ela não cita `app.py`**, enquanto §3, §5
e §7 citam. O agente tinha a evidência na mão e marcou ✅ mesmo assim.

Isso é `🟡 parcial`, e o "o que falta" é **interface**.

### Por que isto é o pior erro possível neste documento

Este mapa existe para ser mostrado a um auditor. Um ✅ errado não é imprecisão de
documentação: é o sistema afirmando conformidade que não tem, no único documento que
alguém vai ler para conferir. Um ❌ honesto é infinitamente melhor que um ✅ otimista —
o primeiro vira tarefa, o segundo vira surpresa na fiscalização.

### O que mudou desde a primeira tentativa

Entre a escrita desta spec e agora, **seis telas da Fase B foram ligadas** (§3, §5, §7,
§7.3, §8, §11). Então vários ✅ que antes seriam parciais agora são legítimos — o mapa
precisa refletir o estado de hoje, não o de julho. **A exceção é §6**, que segue sem tela.

Antes de marcar qualquer ✅, confirme com:

```bash
grep -n "db\.<repositorio>\.\|<repositorio>\." app.py
```

Se a exigência é visível ao usuário e o `grep` não acha nada, é `🟡 parcial`.

### Defeito 2 — caminho absoluto do worktree

O documento trazia um link
`file:///d:/%C3%81rea%20de%20Trabalho/AgroTop-0032/docs/regulatorio/...`, que é o caminho
da máquina onde o agente rodou. Não abre para mais ninguém e vaza o nome do worktree.
**Use caminho relativo ao repositório.**

### Teste que passa a ser obrigatório

Além dos quatro originais:

```python
def test_nenhum_link_e_caminho_absoluto()
    # nada de file://, nada de C:\ ou /d:/ no documento
```

E o quinto critério de aceite abaixo.

## O que fazer

Leia `docs/regulatorio/requisitos_sistema_pnib_rs.md` inteiro e produza uma tabela, seção
por seção, com:

| § | Exigência | Situação | Onde |
|---|---|---|---|
| §4.1 | identificador interno imutável | ✅ atendido | `repositories/animais.py` (`novo_uuid`), migration `0002` |
| §7.2 | gêmeos ligados ao mesmo parto | ✅ atendido | `repositories/nascimentos.py`, tabela `partos` |
| §12 | leitura RFID | ❌ não atendido | — |

**Situações permitidas:** `✅ atendido` · `🟡 parcial` · `❌ não atendido` ·
`⏳ fora de prazo` (exigível só no futuro) · `➖ não se aplica`.

**`🟡 parcial` precisa dizer o que falta.** "Parcial" sem qualificação é a categoria onde
o autoengano se esconde.

## Regras que tornam o mapa confiável

**Toda linha `✅` cita arquivo e símbolo** — módulo, função ou tabela. Sem isso, a afirmação
não é verificável e o mapa vira propaganda.

**Não confunda "tem tabela" com "atendido".** A Fase B criou os módulos, mas **quase nada
está ligado à interface**. Uma exigência cujo repositório existe e cuja tela não existe é
**🟡 parcial**, e o "o que falta" é "interface". Marcar essas como atendidas seria o erro
mais grave que este documento pode conter.

**Prazos importam.** Identificação oficial para trânsito só é exigível a partir de
**01/01/2033** (§4.1). Isso é `⏳ fora de prazo`, não `❌`.

## O teste

`tests/test_mapa_conformidade.py` verifica que o mapa **não apodrece**:

```python
def test_todo_arquivo_citado_existe()
    # extrai os caminhos do mapa e confere no disco

def test_todo_simbolo_citado_existe()
    # função/classe citada existe no módulo indicado (use ast, não import)

def test_toda_secao_do_pnib_aparece_no_mapa()
    # extrai os "## N." do requisitos_sistema_pnib_rs.md e cobra cada um

def test_parcial_sempre_diz_o_que_falta()
```

É isso que separa esta spec de "escrever um documento": o mapa passa a **quebrar o CI**
quando alguém renomeia um módulo e esquece de atualizá-lo.

## Critério de aceite

1. Todas as seções numeradas do documento de requisitos aparecem no mapa.
2. Os quatro testes passam.
3. O resumo no topo traz a contagem por situação — e ela **bate** com a tabela.
4. Nenhuma exigência marcada `✅` sem arquivo e símbolo citados.
5. **Toda exigência visível ao usuário marcada `✅` cita `app.py`.** Foi a ausência disso
   que deixou §6 passar como atendido — e a linha já mostrava a falta, bastava olhar.
6. Nenhum caminho absoluto no documento.

## Proibições

- ❌ **Não implemente nada.** Achou lacuna, registra. Implementar aqui misturaria
  levantamento com mudança, e ninguém saberia se o mapa descreve o sistema ou o desejo.
- ❌ Não altere `docs/regulatorio/requisitos_sistema_pnib_rs.md` — é o texto de referência.
- ❌ Não marque `✅` para exigência cujo repositório existe mas cuja interface não. Isso é
  `🟡 parcial`. **Foi este o defeito da primeira tentativa**, no §6 — e a spec já dizia
  isto naquela ocasião. Se você marcar um ✅ sem `app.py` numa exigência que o usuário
  precisa ver, justifique na linha por que aquela exigência não precisa de tela.
- ❌ Não toque em `app.py`, `database.py`, `repositories/`, `services/`.

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t .
git diff --stat origin/main
```

## Entrega

PR para `main`. No corpo, **a contagem por situação** e as **três lacunas que você considera
mais relevantes** — com uma frase cada dizendo por que importam. Esse resumo é o produto
real desta spec; a tabela é o lastro.
