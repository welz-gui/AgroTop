# Spec 0032 — 🇧🇷 Mapa de conformidade: cada exigência do PNIB e onde ela está

- **Tipo:** documentação verificável · **Risco:** baixo · **Esforço:** 2 dias
- **Branch:** `feat/mapa-de-conformidade`
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

## Proibições

- ❌ **Não implemente nada.** Achou lacuna, registra. Implementar aqui misturaria
  levantamento com mudança, e ninguém saberia se o mapa descreve o sistema ou o desejo.
- ❌ Não altere `docs/regulatorio/requisitos_sistema_pnib_rs.md` — é o texto de referência.
- ❌ Não marque `✅` para exigência cujo repositório existe mas cuja interface não. Isso é
  `🟡 parcial`.
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
