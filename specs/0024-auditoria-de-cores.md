# Spec 0024 — Auditoria de cores: mapear os hex de `app.py` para tokens

- **Tipo:** ferramenta · **Risco:** baixo · **Esforço:** 1 dia
- **Branch:** `feat/auditoria-de-cores`
- **Crie:** `tools/auditar_cores.py` e `tests/test_auditar_cores.py` — **arquivos novos**

---

## Regra de ouro desta spec

Você cria **arquivos novos**. **Não altere `app.py` nem `ui/tema.py`.** Esta ferramenta
**mede e propõe**; quem substitui é a spec 0007, depois, com o resultado desta em mãos.

## Por que isto existe

A [spec 0007](0007) está bloqueada desde o começo do projeto: são ~198 hex literais em
`app.py` para trocar por tokens de `ui/tema.py`, e não havia como **provar** que a troca não
mudou a aparência. Verificar tela por tela, a olho, não é verificação.

A saída é mais barata do que parece. Se `#4ade80` vira `cores["sucesso"]` e
`cores["sucesso"] == "#4ade80"`, a aparência **não pode** ter mudado — é identidade, não
semelhança. Isso transforma um problema visual num problema de string, que é testável.

**Esta spec entrega o mapa.** Sem ele, ninguém sabe quantos hex têm token exato, quantos não
têm, e quais.

## Contrato obrigatório

```python
def extrair_hex(codigo: str) -> list[dict]:
    """Todos os hex literais de um código Python.

    Retorna [{"hex": "#4ade80", "linha": int, "contexto": str}, ...]
    `contexto` é o trecho da linha, para o humano reconhecer onde está.
    Normaliza para minúsculo e forma longa (#abc -> #aabbcc).
    """


def mapear(hexes: list[dict], tema: dict) -> dict:
    """Casa cada hex com o token de mesmo valor.

    `tema`: {"escuro": {"sucesso": "#4ade80", ...}, "claro": {...}}

    Retorna:
        {
          "exatos":   [{"hex": str, "token": str, "ocorrencias": int}, ...],
          "sem_token":[{"hex": str, "ocorrencias": int,
                        "mais_proximo": str, "distancia": float}, ...],
          "resumo": {"total": int, "distintos": int,
                     "com_token": int, "sem_token": int},
        }
    """


def distancia(hex_a: str, hex_b: str) -> float:
    """Distância perceptual entre duas cores, 0 = idênticas."""
```

**Assine exatamente assim.**

## Sobre `distancia` e `mais_proximo`

O mantenedor decidiu: **hex sem token exato ganha token novo, aproximado ao existente mais
próximo.** `mais_proximo` é o que sustenta essa decisão — ele responde *"de qual token essa
cor está perto?"*, para o humano julgar se vale um token novo ou se dá para reaproveitar.

Use **CIE76 sobre L\*a\*b\***, não distância euclidiana em RGB. Em RGB, dois azuis
visualmente idênticos podem ficar mais "longe" que um azul e um roxo distinguíveis — o
espaço não é perceptual, e o número enganaria justamente quem confia nele.

Se preferir não adicionar dependência, converta você mesmo (sRGB → XYZ → Lab é aritmética
fechada, ~25 linhas). **Justifique a escolha no PR.**

## Saída da ferramenta

Rodar `python tools/auditar_cores.py` imprime um relatório legível:

```
198 hex em app.py · 41 distintos
  com token exato:  33 (176 ocorrências)
  sem token:         8 (22 ocorrências)

SEM TOKEN (candidatos a token novo)
  #1e293b  12x  mais próximo: fundo_card (#1e2937), distância 2.1
  #f87171   4x  mais próximo: perigo (#ef4444),     distância 8.7
  ...
```

## Critério de aceite

1. `extrair_hex` acha hex em f-string, em `st.markdown`, em dicionário e em CSS embutido —
   os quatro lugares onde eles aparecem em `app.py`.
2. Não confunde `#` de comentário nem `#` de fragmento de URL com cor.
3. `#abc` e `#AABBCC` normalizam para a mesma forma.
4. `distancia(x, x) == 0` e a distância entre preto e branco é a máxima da escala.
5. **Rodar contra o `app.py` real produz o relatório sem estourar** — cole o resultado no PR.
6. `mapear` com tema vazio devolve tudo em `sem_token`, sem erro.

## Proibições

- ❌ **Não altere `app.py`.** Substituir é a spec 0007, e ela depende do resultado desta.
- ❌ Não altere `ui/tema.py` — propor token novo é saída de relatório, não edição.
- ❌ Não toque em `database.py`, `repositories/`, `services/`.
- ❌ Não crie tabela nem migration.

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t .
python tools/auditar_cores.py
git diff --stat origin/main
```

## Entrega

PR para `main`, pronto para revisão. **Cole o relatório completo no corpo do PR** — ele é o
produto desta spec, e é o que vai destravar a 0007. Diga também quantos tokens novos você
estima que serão necessários.
