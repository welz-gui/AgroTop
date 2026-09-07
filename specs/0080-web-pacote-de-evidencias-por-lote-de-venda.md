# Spec 0080 — Web: pacote de evidências por lote de venda

- **Tipo:** implementação · **Risco:** médio · **Esforço:** 2-3 dias
- **Branch:** `feat/web-pacote-de-evidencias`
- **Altere:** `app.py` (nova aba em `page_relatorios`), e os testes correspondentes.
  **Não crie repositório novo** — toda leitura já existe em `repositories/financeiro.py`,
  `repositories/sanidade.py`, `repositories/pesagens.py`, `database.py::get_photos`
- **Pré-requisito:** nenhum — `sales`, `medications`, `weighings`, `animal_photos` e
  `services.rentabilidade.por_lote_de_venda` já existem, testados, em produção

---

## Regra de ouro desta spec (não negociável)

Este documento vai para **fora da fazenda** — comprador, frigorífico, cooperativa. Duas
coisas não podem acontecer:

1. **Nenhum dado financeiro interno.** `cost_at_sale`, `profit`, margem, custo por
   arroba/kg — nada disso aparece no pacote. É informação de negociação do produtor, não
   evidência de origem/sanidade. `_fin_rentabilidade_por_raca`/`por_lote_de_venda` calculam
   isso para uso **interno** (spec 0042/Trilha 3); esta spec não reexpõe esse número em
   nenhum campo, rótulo ou nota do PDF.
2. **Nenhuma promessa de certificação.** O pacote **organiza** registros que já existem no
   sistema — não é auditoria, não é certificação legal, não é garantia de conformidade com
   PNIB/EUDR/programa nenhum. Mesmo aviso, mesma frase-base que `app.py::_dash_conformidade`
   já usa há semanas: **"não é avaliação de conformidade legal nem certificação oficial"**.
   Esse aviso é obrigatório, visível, na capa do PDF — não em rodapé pequeno.

## Objetivo

"Lote de venda" é o agrupamento de `sales` que compartilham `lot_ref` — **não confunda
com `lotes`** (piquete/agrupamento zootécnico, tabela diferente, `lote_id`). Um lote de
venda é o conjunto de animais vendidos juntos, ao mesmo comprador, na mesma operação
(`services/rentabilidade.py::por_lote_de_venda` já define e agrupa isso, spec 0042/Trilha
3, item que fechou a trilha).

Hoje, se o produtor precisa provar origem/sanidade de um lote vendido para o comprador,
ele monta isso manualmente, catando dado tela por tela. Esta spec gera um PDF único —
identificação, origem, histórico de pesagem, histórico sanitário/carência e (se houver)
foto mais recente de cada animal do lote — pronto para entregar.

**Isto é nível 1-2 de rastreabilidade** (gestão interna organizada + compartilhamento com
comprador), não nível 3 (conformidade auditável formal — ver `docs/adr/0004-conformidade-pnib.md`).
Não tente ser as três coisas nesta spec.

## Contexto que você precisa

- `repositories/financeiro.py::get_sales(start_date=None, end_date=None) -> list[dict]`
  — já faz `LEFT JOIN` com `animals` (`breed`, `sex`, `carcass_yield`), inclui `lot_ref`,
  `animal_id`, `animal_uuid`, `buyer`, `sale_date`, `sale_type`. **Não crie uma query
  nova** — filtre o resultado dela em Python por `lot_ref`.
- `services/rentabilidade.py::por_lote_de_venda(vendas)` já sabe agrupar vendas por
  `lot_ref`, tratando `lot_ref=None` como "um lote de 1 cabeça cada" (não misture vendas
  avulsas entre si). **Reuse essa mesma regra de agrupamento** para listar as opções de
  "lote de venda" na UI — não reimplemente o agrupamento.
- `repositories/sanidade.py::get_medications(animal_id) -> list[dict]` (`medication_name`,
  `dose`, `unit`, `application_route`, `withdrawal_days`, `med_date`, `applied_by`,
  `notes`) e `get_withdrawal_end(animal_id) -> Optional[date]` (carência ativa).
- `repositories/pesagens.py::get_weighings(animal_id) -> list[dict]` — histórico completo
  de pesagem do animal.
- `database.py::get_photos(animal_id) -> list[dict]` (`id`, `taken_date`, `operator`,
  `mime`, sem os bytes) e `get_photo_image(photo_id) -> (bytes, mime)` — use a **mais
  recente** (`taken_date` maior) só, não anexe o histórico de fotos inteiro.
- `animals.gta_number`, `animals.nf_number`, `animals.fornecedor_name` (ou o relacionamento
  equivalente já usado em `page_relatorios::rt1`, linhas ~4137-4154) — é a mesma fonte que
  a aba "🐄 Inventário" já usa para as colunas "Fornecedor"/"NF"/"GTA". Reuse a mesma
  extração, não invente um segundo caminho para o mesmo dado.
- `app.py::_pdf_safe`/`_df_to_pdf` (linhas ~447-511) — padrão de PDF já usado no projeto
  (fpdf2, fonte Helvetica/Latin-1, sanitização de emoji). **Esta spec precisa de um layout
  novo** (não é uma tabela simples — é uma capa + uma seção por animal), então não force
  o pacote inteiro dentro de `_df_to_pdf`; escreva uma função nova que usa `FPDF`
  diretamente, mas **reuse `_pdf_safe`** para todo texto.
- `fpdf2` já está em `requirements.txt` e suporta `pdf.image()` a partir de um buffer de
  bytes (`io.BytesIO`) — não precisa salvar em disco.

## Contrato obrigatório

### Nova aba em `page_relatorios` (rt4: "📦 Pacote de Evidências")

1. Seletor do lote de venda: liste os grupos que `por_lote_de_venda` já calcula (rótulo:
   `lot_ref` quando existir, senão "Venda avulsa — {animal_id} ({sale_date})"), mais
   recente primeiro.
2. Botão "Gerar PDF" — sob demanda, não gera a cada rerun.
3. PDF gerado, em ordem:
   - **Capa:** título "AgroTop — Pacote de Evidências", comprador (`buyer`), data(s) da
     venda, quantidade de animais, e o **aviso obrigatório** da Regra de Ouro item 2, em
     destaque (não rodapé).
   - **Uma seção por animal** do lote: ID/brinco, raça, sexo, categoria/idade, origem
     (fornecedor, NF, GTA), foto mais recente (se houver — se não houver, omita a seção de
     foto sem erro), tabela de pesagens (data, peso, método, operador), tabela de
     sanidade/medicamentos (data, medicamento, dose, carência em dias, aplicado por), e
     status de carência atual ("Livre" ou "Em carência até DD/MM/AAAA").
4. `st.download_button` com nome de arquivo
   `agrotop_evidencias_{lot_ref_ou_id}.pdf`.

### Função de geração (nova, em `app.py` — não precisa de módulo `services/` novo:
é composição de leitura pura, não regra de negócio nova)

```python
def _gerar_pacote_evidencias(vendas_do_lote: list[dict]) -> bytes:
    """Monta o PDF de evidências para um lote de venda (spec 0080).

    `vendas_do_lote` é a fatia de get_sales() que partilha o mesmo lot_ref
    (ou uma venda avulsa sozinha). Não inclui nenhum dado financeiro interno
    (custo, lucro, margem) — só identificação, origem, pesagem e sanidade.
    """
```

## Critério de aceite

1. Lote de venda com 3+ animais → PDF com uma capa e 3+ seções, uma por animal, cada uma
   com os dados corretos daquele animal especificamente (teste comparando contra
   `get_medications`/`get_weighings` chamados direto no teste, prova real — mesmo padrão
   da spec 0075).
2. Venda avulsa (`lot_ref=None`) → PDF de 1 animal, sem erro, sem misturar com outra venda
   avulsa do mesmo dia.
3. Animal sem foto → seção gerada normalmente, sem a imagem, sem exceção.
4. Animal sem carência ativa → "Livre" aparece; animal em carência → data correta de fim.
5. **Nenhum campo do PDF contém `cost_at_sale`, `profit`, `custo`, `margem` ou qualquer
   valor monetário de custo interno** — teste isso extraindo o texto do PDF gerado (fpdf2
   permite reabrir com uma lib de leitura, ou teste indiretamente confirmando que a função
   de geração nunca lê esses campos de `vendas_do_lote`).
6. O aviso "não é avaliação de conformidade legal nem certificação oficial" (ou
   equivalente) está presente no texto da capa — teste extraindo o texto do PDF.
7. `flake8`/`ruff` e a suíte inteira verdes (`AGROTOP_FORCE_SQLITE=1 python -m unittest
   discover -s tests -t . -v`).

## Proibições

- ❌ Não inclua `cost_at_sale`, `profit`, margem, custo por arroba/kg ou qualquer número
  financeiro interno — é a proibição central desta spec.
- ❌ Não prometa certificação, conformidade legal ou aprovação de auditoria em nenhum
  texto do PDF.
- ❌ Não confunda "lote de venda" (`sales.lot_ref`) com "lote" (piquete, `lotes.id`) em
  nenhum nome de variável, rótulo ou comentário — são conceitos diferentes no mesmo
  projeto, e essa confusão já causou retrabalho em specs anteriores da Trilha 3.
- ❌ Não inclua histórico de movimentação entre propriedades (GTA de trânsito,
  `repositories/movimentacoes.py`) nem cadeia completa de custódia — fora de escopo desta
  spec (é nível 3, conformidade auditável formal; ver ADR 0004). Só o `gta_number` já
  gravado no cadastro do animal.
- ❌ Não anexe mais de uma foto por animal, nem o histórico de fotos inteiro — só a mais
  recente, para manter o PDF leve.
- ❌ Não crie endpoint de API nem tela mobile para isto — é relatório de mesa (comprador
  recebe por e-mail/impresso), mesmo raciocínio de exclusão que a ADR 0007 já aplica a
  `page_financeiro`.
- ❌ Não altere `services/rentabilidade.py`, `repositories/financeiro.py`,
  `repositories/sanidade.py` nem `repositories/pesagens.py` — esta spec só lê o que já
  existe.

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t . -v
python -m compileall app.py tests
```

## Entrega

PR para `main`, pronto para revisão. Confirme no corpo do PR que o PDF gerado em teste
real não contém nenhuma palavra de custo/lucro (cole o resultado do teste do critério 5) e
que o aviso de não-certificação aparece na capa (cole o texto exato).
