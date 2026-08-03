# Spec 0030 — 🇧🇷 Leitura de arquivo de lote de brincos (função pura)

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 1 dia
- **Branch:** `feat/arquivo-lote-brincos`
- **Crie:** `services/arquivo_dispositivos.py` e `tests/test_arquivo_dispositivos.py`

---

## Regra de ouro desta spec

Você cria **arquivos novos**. **Não altere nenhum arquivo existente.**

## Objetivo

O §5.3 exige **"importação de lotes por arquivo"**. Hoje `repositories/dispositivos.py`
importa por faixa (`BR0001` a `BR0100`), o que serve quando os números são contínuos — e
não é o caso quando o fabricante entrega uma planilha com visual e eletrônico pareados,
ou quando a faixa tem buracos.

Esta função lê o arquivo e devolve a lista pronta, sem tocar banco.

## Contrato obrigatório

```python
def ler(texto: str) -> dict:
    """Interpreta um arquivo de lote de dispositivos.

    Aceita CSV com `;` ou `,`, com ou sem cabeçalho. Colunas reconhecidas
    (em qualquer ordem, nomes tolerantes a acento e caixa):
      codigo_visual (obrigatória) · codigo_eletronico · tipo · fabricante ·
      modelo · lote · data_fabricacao

    Retorna {
      "aceitos":   [{"codigo_visual","codigo_eletronico","tipo",...}, ...],
      "rejeitados":[{"linha": int, "conteudo": str, "motivo": str}, ...],
      "duplicados_no_arquivo": [str, ...],
      "total_linhas": int,
      "colunas_detectadas": [str, ...],
    }
    """


def conferir_pareamento(itens: list[dict], *,
                        digitos_comparados: int = 0) -> list[dict]:
    """Divergências entre visual e eletrônico no próprio arquivo (§5.3).

    Usa `services.estados_dispositivo.conferir_codigos` — **não reimplemente**.
    Retorna [{"codigo_visual", "codigo_eletronico", "divergencia"}, ...]
    """
```

**Assine exatamente assim.**

## O que separa esta função de um `csv.reader`

**Duplicidade dentro do próprio arquivo.** Fabricante repete linha; se as duas entrarem,
dois dispositivos ficam com o mesmo código e o índice único do banco estoura no meio da
importação, deixando metade importada. Detectar antes é o que permite o usuário decidir.

**Cabeçalho com acento e caixa variável.** `Código Visual`, `CODIGO_VISUAL` e
`codigo visual` são a mesma coluna. Normalize.

**Linha ruim não derruba o arquivo.** Uma linha com código vazio vira `rejeitado` com
motivo; as outras 999 continuam. Arquivo de fabricante quase sempre tem lixo no rodapé.

## Critério de aceite

1. CSV com cabeçalho `Código Visual;Código Eletrônico` é lido corretamente.
2. O mesmo arquivo sem cabeçalho também — a primeira linha vira dado, não é descartada.
3. Código visual repetido aparece em `duplicados_no_arquivo` **e não é duplicado** em
   `aceitos`.
4. Linha vazia e linha de rodapé (`"Total: 100"`) viram `rejeitados` com motivo legível.
5. `conferir_pareamento` com `digitos_comparados=6` casa `BR0001` com `9820000000BR0001`
   — é o caso real, porque o eletrônico carrega prefixo de país que o visual não mostra.
6. Texto vazio devolve tudo zerado, sem estourar.
7. Arquivo com 10 mil linhas não demora nem consome memória desproporcional.

## Proibições

- ❌ Não toque em `app.py`, `database.py`, `repositories/`, `ui/`, nem em módulo existente
  de `services/`.
- ❌ **Não reimplemente `conferir_codigos`** — importe de
  `services/estados_dispositivo.py` (R8).
- ❌ Não consulte banco nem grave nada. Quem grava é o repositório, depois.
- ❌ Não adicione `pandas` — `csv` da biblioteca padrão basta, e o `requirements.txt` da
  raiz alimenta o deploy.
- ❌ **Não valide formato de código oficial.** O formato do PNIB ainda não foi publicado
  (§23), e inventar máscara recusaria arquivo válido.

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t .
git diff --stat origin/main
```

## Entrega

PR para `main`. No corpo, cole um exemplo de arquivo com **linha duplicada e rodapé de
totais**, e o resultado da leitura — é o formato que chega do fabricante de verdade.
