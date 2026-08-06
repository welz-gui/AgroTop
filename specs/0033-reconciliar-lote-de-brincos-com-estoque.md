# Spec 0033 — Reconciliar um lote de brincos importado com o estoque já cadastrado

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 1 dia
- **Branch:** `feat/reconciliar-lote-brincos`
- **Crie:** `services/reconciliacao_dispositivos.py` e
  `tests/test_reconciliacao_dispositivos.py` — **arquivos novos**

---

## Regra de ouro desta spec

Você cria **um arquivo novo**. **Não altere nenhum código de produção** —
nem `app.py`, nem `database.py`, nem `repositories/`, nem outro módulo de `services/`.
Se encontrar um jeito melhor de ligar isto à tela, **anote no PR — não implemente.**

## Contexto: o que já existe e por que não basta

`services/arquivo_dispositivos.py` (spec 0030) já sabe ler um arquivo de lote de brincos e
devolver `{"aceitos": [...], "rejeitados": [...], "duplicados_no_arquivo": [...]}`. Ele
resolve duplicata **dentro do próprio arquivo**. O que ele não pode resolver — porque não
toca banco (R9) — é duplicata **contra o estoque que já existe**: um `codigo_visual` que já
está em `dispositivos` (em qualquer situação que não seja "pode ser reaproveitado") não pode
virar uma segunda linha na tabela, e hoje nada verifica isso antes da gravação.

## Objetivo

Uma função pura que recebe a saída de `arquivo_dispositivos.ler()` **mais** o conjunto de
códigos que já existem no estoque, e devolve a decisão final por linha: grava, pula por já
existir, ou pula por conflito de tipo.

## Contrato obrigatório

```python
def reconciliar(
    itens_do_arquivo: list[dict],      # o "aceitos" de arquivo_dispositivos.ler()
    codigos_em_estoque: dict[str, str],  # {"BR0001": "disponivel", "BR0002": "aplicado", ...}
) -> dict:
    """
    Cada item de `itens_do_arquivo` tem pelo menos `codigo_visual`. `codigos_em_estoque`
    mapeia código -> status atual (qualquer valor de
    `services.estados_dispositivo.ESTADOS`).

    Retorna {
        "para_gravar":  [dict, ...],  # itens que não colidem com nada em estoque
        "ja_existentes": [
            {"codigo_visual": str, "status_atual": str}, ...
        ],
        "resumo": {"total": int, "para_gravar": int, "ja_existentes": int},
    }
    """
```

## Regras que decidem a correção

**Um código em estado definitivo (`inutilizado`, `devolvido`, `cancelado`) não bloqueia
reimportação.** Releia `services/estados_dispositivo.py`: esses estados são terminais
porque *aquele número não deve ser reaplicado* — não porque o código nunca mais pode
aparecer num arquivo. Um código que já está `inutilizado` e reaparece no arquivo do
fornecedor é **erro do fornecedor** e precisa ir para `ja_existentes` com o status atual
visível, para alguém decidir — não pode virar um segundo registro silenciosamente.

**Qualquer status conta como "já existe".** Não filtre por "só os ativos" — o objetivo
desta função é nunca deixar um `codigo_visual` duplicado entrar na tabela, e isso vale
para os 12 estados, sem exceção. `repositories/dispositivos.importar_lote` já pula
duplicata **dentro** da faixa numérica pelo mesmo motivo; esta função faz o equivalente
para um arquivo com códigos arbitrários (não numa faixa contínua).

**A ordem de `para_gravar` é a ordem de entrada.** Não reordene — quem vai gravar pode
depender da ordem para relacionar com o índice da linha original do arquivo.

**Item sem `codigo_visual`** (não deveria acontecer, já que `arquivo_dispositivos.ler()`
só aceita linhas com o campo preenchido) — trate como `ja_existentes` com
`status_atual: "sem_codigo"`, não estoure.

## Critério de aceite

1. Nenhum código presente em `codigos_em_estoque` aparece em `para_gravar`.
2. Item com código ausente de `codigos_em_estoque` vai para `para_gravar`, inalterado.
3. `resumo["total"] == resumo["para_gravar"] + resumo["ja_existentes"]` sempre.
4. Testado com os 12 estados de `services/estados_dispositivo.ESTADOS`, um a um, como
   status atual de um código que reaparece no arquivo — todos vão para `ja_existentes`.
5. 500 itens no arquivo, 500 já em estoque, todos duplicados: `para_gravar` vazio,
   nada trava nem demora perceptivelmente (é dict lookup, não deveria ser O(n²)).
6. Lista vazia de qualquer um dos dois parâmetros não estoura.

## Proibições

- ❌ Não importe nem chame `repositories/dispositivos.py` — este módulo não toca banco.
- ❌ Não decida qual status é "válido para reaproveitar". Isso é decisão de quem grava
  (o mantenedor, na integração); aqui só se classifica "existe" vs "não existe".
- ❌ Não crie tabela nem migration.
- ❌ Não toque em `services/arquivo_dispositivos.py` — ele já está correto e testado.

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t .
git diff --stat origin/main
```

## Entrega

PR para `main`. No corpo, um exemplo antes/depois com uns 5 itens (2 novos, 3 já em
estoque em estados diferentes) mostrando a saída completa.
