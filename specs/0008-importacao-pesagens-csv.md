# Spec 0008 — Importação de pesagens por CSV (parser puro)

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 1–2 dias
- **Branch:** `feat/importacao-pesagens`
- **Crie:** `services/importacao.py` e `tests/test_importacao.py` — **arquivos novos**

---

## Regra de ouro desta spec

Você cria **arquivos novos** em `services/` e `tests/`. **Não altere nenhum arquivo
existente** — nem `database.py`, nem `app.py`, nem outros módulos de `services/`.

A ligação com a interface e o banco é feita depois, pelo mantenedor. Seu produto é uma
**função pura, testada e com contrato claro**. É isso que permite que esta tarefa avance
em paralelo ao refactor da Fase A.

## Objetivo

Hoje a pesagem é digitada uma a uma. Indicadores de balança exportam arquivo de sessão, e
importar esse arquivo elimina digitação e erro — vale mesmo depois que houver Bluetooth,
porque pareamento falha no campo.

## Contrato obrigatório

```python
def parse_pesagens(
    texto: str,
    *,
    ids_conhecidos: set[str] | None = None,
) -> dict:
    """Interpreta um CSV de pesagens.

    `ids_conhecidos`: brincos existentes no rebanho. Se None, não valida existência.
    (É injetado justamente para a função não precisar do banco.)

    Retorna:
        {
          "aceitas":   [{"animal_id": str, "peso": float, "data": "YYYY-MM-DD"}, ...],
          "rejeitadas":[{"linha": int, "conteudo": str, "motivo": str}, ...],
          "total_linhas": int,
        }
    """
```

**Assine exatamente assim.** O mantenedor vai ligar essa função à UI; mudar a assinatura
quebra a integração.

## Regras de interpretação

- **Separador:** detectar `,` e `;` automaticamente (planilha brasileira usa `;`).
- **Decimal:** aceitar `450.5` **e** `450,5`.
- **Datas:** aceitar `AAAA-MM-DD` e `DD/MM/AAAA`. **Sempre devolver em ISO**
  (`AAAA-MM-DD`) — é o formato do projeto ([ROADMAP.md](../ROADMAP.md) R5).
- **Cabeçalho:** detectar e ignorar se presente.
- **Linha vazia:** ignorar sem contar como rejeitada.

## Motivos de rejeição (cada um com mensagem em português, legível)

| Situação | Exemplo de motivo |
|---|---|
| Colunas de menos | `"esperado 3 colunas, encontrado 2"` |
| Peso não numérico | `"peso inválido: 'abc'"` |
| Peso fora de faixa (≤ 0 ou > 1500 kg) | `"peso fora da faixa plausível: 2300 kg"` |
| Data inválida | `"data inválida: '32/13/2026'"` |
| Data no futuro | `"data no futuro: 2027-01-01"` |
| Brinco desconhecido (só se `ids_conhecidos` vier) | `"animal não encontrado: BR9999"` |
| Brinco vazio | `"brinco vazio"` |

**Nenhuma linha ruim pode derrubar a importação.** Uma linha inválida vira rejeitada; as
demais seguem.

## Testes obrigatórios

`tests/test_importacao.py` cobrindo: caminho feliz, os dois separadores, os dois formatos
de data, decimal com vírgula, cada motivo de rejeição, arquivo vazio, só cabeçalho, e
arquivo misto (aceitas + rejeitadas juntas).

## Critério de aceite

1. `parse_pesagens` respeita o contrato acima **exatamente**.
2. Todo motivo de rejeição tem teste.
3. `services/importacao.py` **não importa** `streamlit`, `database`, `repositories` nem
   `sqlite3`/`psycopg2` — é função pura ([ROADMAP.md](../ROADMAP.md) R9).
4. A suíte inteira fica verde (72 + os seus).

## Proibições

- ❌ Não altere arquivo existente. Só crie os dois novos.
- ❌ Não grave no banco, não leia do banco, não importe `database`.
- ❌ Não mexa na interface — a tela de importação é trabalho posterior.
- ❌ Não adicione dependência: `csv` e `datetime` da biblioteca padrão bastam.

## Como verificar antes de abrir o PR

```bash
python -m unittest discover -s tests -t . -v
python -m compileall app.py database.py repositories services ui tests tools
git diff --stat origin/main    # deve mostrar apenas os 2 arquivos novos
```

## Entrega

PR para `main` mostrando um exemplo real de entrada e a saída correspondente — inclusive
com linhas rejeitadas, que é a parte que o usuário mais vai ver.
