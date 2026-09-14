# Spec 0099 — Web: formatação pt-BR consistente de números e datas

- **Tipo:** manutenção · **Risco:** médio · **Esforço:** 1-2 dias
- **Branch:** `fix/web-formatacao-pt-br`
- **Altere:** `app.py` (só chamadas de formatação, sem mudar lógica/dado), `tools/` (script
  de auditoria novo, mesmo padrão de `tools/auditar_cores.py`), testes correspondentes
- **Pré-requisito:** nenhum

---

## Objetivo

Metade web do item RD03 da proposta de redesign
(`DESIGN-IS-2026-09-10/proposta-specs-redesign-para-revisao-claude.md`) — separada da metade
mobile ([spec 0098](0098-mobile-linguagem-operacional-pt-br.md)). **Achado ao investigar,
mais restrito do que a proposta original sugeria**: as mensagens específicas citadas na
proposta ("Pesagem atrasada", "Peso-alvo atingido") **já existem com essa redação exata** no
web (`"peso-alvo atingido"` em `app.py:5154`; seção "🔴 Animais Sumidos" já é o rótulo usado,
tanto no web quanto no mobile desde a spec 0087) — **não precisam de mudança**. O gap real e
mensurável é outro: formatação de número e data inconsistente, espalhada pelo arquivo
inteiro.

## Contexto que você precisa

- **`_num_br(v, casas=1)`** (`app.py:256`) já existe e já funciona — o problema não é falta
  de helper, é uso inconsistente. `grep -cE ':\.[0-9]f}' app.py` encontra **97 ocorrências**
  de formatação decimal direta em Python (`f"{valor:.1f}"`), a esmagadora maioria sem passar
  por `_num_br`.
- **Datas** têm o mesmo problema: `_evidencias_data()` (`app.py:535`) formata certo
  (`%d/%m/%Y`) mas é uma função privada, escopada só à spec 0080 (pacote de evidências) — não
  existe um helper de data de uso geral. `grep -cE "\.isoformat\(\)" app.py` encontra 47
  ocorrências, e há pelo menos 5 lugares com `.strftime('%d/%m/%Y')` reescrito à mão
  (`app.py:540,1177,2392,4999` e a linha 324 com variante `%d/%m (%a)`).
- **Nem toda ocorrência de `.isoformat()`/`:.Nf}` é texto visível ao usuário** — muitas são
  para CSV, exportação, log ou string interna. **Não converta às cegas.** Use o mesmo método
  da spec 0007 (hex→tokens): audite primeiro, classifique, só então troque.
- **Mesmo método da spec 0007** (`tools/auditar_cores.py` é o precedente direto): escreva
  `tools/auditar_formatacao.py` que varre `app.py`, lista cada ocorrência com linha e
  contexto (a string ao redor), e categoriza em "visível ao usuário" vs. "interno/exportação"
  — o critério prático: está dentro de um `st.write`/`st.metric`/`st.markdown`/f-string
  passada a um componente Streamlit visível, ou está indo para `csv`/`io`/log/nome de
  arquivo? A segunda categoria fica intacta.

## Contrato obrigatório

1. **`tools/auditar_formatacao.py`** (novo, mesmo padrão de `tools/auditar_cores.py`):
   produz uma lista de todas as ocorrências de formatação decimal/data em `app.py`, com
   linha, trecho e classificação (visível/interno). Rode e cole o resumo no PR.
2. **Toda ocorrência classificada como "visível ao usuário"** de formatação decimal passa a
   usar `_num_br(...)` em vez do format-spec Python direto.
3. **Novo helper `_data_br(value) -> str`**, mesma assinatura/comportamento de
   `_evidencias_data` (pode reaproveitar o corpo dela, promovendo para função de uso geral —
   não duplique a lógica) — formata `date`/`datetime`/string ISO para `DD/MM/AAAA`, `"—"`
   para vazio/`None`.
4. **Toda ocorrência de data classificada como "visível ao usuário"** passa a usar
   `_data_br(...)`. Datas indo para CSV, nome de arquivo, ou qualquer payload não-visual
   continuam como estão.
5. **Não mude nenhuma mensagem de texto** (rótulos, avisos, nomes de seção) — já confirmado
   que "peso-alvo atingido" e "Sumidos" já estão corretos. Esta spec é só formatação de
   número/data, não redação.

## Critério de aceite

1. `tools/auditar_formatacao.py` roda sem erro e produz a lista completa das 97+47
   ocorrências, classificadas.
2. Todas as ocorrências marcadas "visível ao usuário" convertidas — confirmado por um teste
   que reroda o audit depois da mudança e confirma zero ocorrências visíveis restantes sem
   `_num_br`/`_data_br`.
3. Ocorrências "internas/exportação" — mesma contagem antes/depois (nenhuma convertida por
   engano, nenhuma esquecida da lista original).
4. Nenhuma prova de UI existente (`tests/ui_*_prova.py`) quebra — número/data mudando de
   formato pode quebrar asserção de texto exato; ajuste as que comparam string literal.
5. `python -m unittest discover -s tests -t .` verde.

## Proibições

- ❌ Não troque formatação em CSV, nome de arquivo, log ou qualquer string que não seja
  renderizada como texto visível — o audit tool existe exatamente para não confiar em
  "parece visível" sem checar o contexto real de cada ocorrência.
- ❌ Não mude nenhuma mensagem/rótulo — confirmado que os dois exemplos citados na proposta
  original (peso-alvo, Sumidos) já estão certos; não reabra decisão de redação nesta spec.
- ❌ Não toque `mobile/` — metade mobile é a [spec 0098](0098-mobile-linguagem-operacional-pt-br.md).
- ❌ Não crie dependência nova (`babel`, `locale` do stdlib) — `_num_br`/`_data_br` continuam
  sendo funções puras de poucas linhas, mesmo padrão do que já existe.

## Como verificar antes de abrir o PR

```bash
$env:AGROTOP_FORCE_SQLITE = "1"
python tools/auditar_formatacao.py
python -m unittest discover -s tests -t .
```

## Entrega

PR para `main`, pronto para revisão. Cole no corpo do PR a saída do `tools/auditar_formatacao.py`
(antes e depois), mostrando quantas ocorrências visíveis foram convertidas e quantas internas
ficaram intactas — mesmo formato de evidência que a spec 0007 exigiu para a troca de cores.
