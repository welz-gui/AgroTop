# Spec 0083 — Web: assistente de consulta por IA (OpenRouter)

- **Tipo:** implementação · **Risco:** médio · **Esforço:** 2-3 dias
- **Branch:** `feat/web-assistente-ia`
- **Altere:** `app.py` (nova página `page_assistente`), `services/assistente_ia.py`
  (novo), e os testes correspondentes. **Nenhuma dependência nova** — `requests` já está
  em `requirements.txt` desde a spec 0079
- **Pré-requisito:** nenhum — `database.py::get_rebanho_stats`/`get_alert_animals` e
  `services/recomendacoes.py::avaliar` já existem, testados, em produção

---

## Regra de ouro desta spec (não negociável)

Esta é a primeira integração do AgroTop com um provedor de IA externo. O relatório
estratégico que originou este objetivo (ver ROADMAP.md, Trilha 4) foi explícito:
**"busca em linguagem natural... sem decisões autônomas"**. Cinco regras, nesta ordem
de importância:

1. **Só leitura, nunca escrita.** O assistente nunca chama `add_*`/`update_*`/
   `register_*`/`atualizar` nem qualquer função que grave no banco. Ele lê um contexto já
   calculado e responde texto — não decide nada, não aciona nada.
2. **Nunca envie tabela crua para a API externa.** Não serializar `animals`, `weighings`,
   `sales`, `medications` linha a linha no prompt. Envie só os **resumos já calculados**
   que a seção "Contexto que você precisa" lista — controla custo (tokens) e exposição de
   dado ao mesmo tempo.
3. **A chave de API nunca é hardcoded.** Vem de `OPENROUTER_API_KEY` via `os.environ`,
   ponto. Ausente → a tela mostra "recurso não configurado", nunca quebra o app (mesmo
   padrão do PWA/ROADMAP R19).
4. **Aviso permanente e visível sobre a natureza do dado enviado.** O nível gratuito do
   OpenRouter (`:free`) pode ter termos de retenção/uso diferentes dos modelos pagos —
   isso foi decidido conscientemente para a v1 (ver "Contexto"), mas o **usuário final do
   AgroTop** (produtor/operador) tem que ver esse aviso na tela, não só o time que
   escreveu o código.
5. **Resposta sempre marcada como gerada por IA, nunca como fato do sistema.** Layout
   deixa claro que aquele texto é interpretação de um modelo externo, não um número
   calculado pelo AgroTop (que já tem seu próprio padrão de exibição em métricas/tabelas).

## Objetivo

Uma caixa de pergunta em linguagem natural sobre o estado atual do rebanho/fazenda —
"quais animais estão em carência?", "o que mudou desde a semana passada?", "por que o
alerta de margem disparou?" — respondida por um modelo de linguagem via **OpenRouter**
(decisão de provedor tomada em conversa com o usuário: free tier `:free` para começar,
com caminho documentado para trocar por um modelo com garantia de "Zero Data Retention"
quando o uso envolver dado sensível de verdade — ver Proibições).

**v1 é deliberadamente pequena:** uma pergunta, um contexto fixo, uma resposta. Sem
memória de conversa, sem resumo automático de ficha de animal, sem relatório narrativo —
esses são os outros modos que o relatório estratégico lista (§6.3), e ficam para specs
futuras, se fizerem sentido depois que esta v1 provar que vale a pena.

## Contexto que você precisa

- **`database.py::get_rebanho_stats() -> AnimalStats`** — já usado pela spec 0075/API
  dashboard (`total`, `avg_weight`, `avg_gmd`, `males`, `females`, `lotacao_ua_ha`, etc.).
- **`database.py::get_alert_animals() -> dict`** — `sumidos`/`carencia`/`prontos`, mesma
  fonte da spec 0063/API de alertas. Envie só as **contagens**, não a lista de animais
  (mesma decisão que a spec 0075 já tomou para o mesmo dado, pela mesma razão — ver
  `specs/0075-api-dashboard-resumo.md`).
- **`services/recomendacoes.py::avaliar(...)`** — o motor de regras (spec 0011, em
  produção desde o PR #29), já produz alertas explicados com motivo
  ("estoque insuficiente", "piquete acima da capacidade", "carência impede abate",
  "GMD abaixo da meta", "margem em risco", "pronto para venda"). **Esta é a fonte
  primária de "o que está acontecendo agora"** — o assistente não deve reinventar
  nenhuma dessas contas, só verbalizar o que o motor de regras já calculou.
- **`OpenRouter`** — API compatível com o formato OpenAI
  (`POST https://openrouter.ai/api/v1/chat/completions`, `Authorization: Bearer
  <chave>`). Use `requests.post` direto, sem SDK — mesmo padrão de `services/ndvi.py`.
  **Verifique o nome do modelo gratuito atual na hora de implementar** (o catálogo de
  modelos `:free` do OpenRouter muda; não hardcode um nome de modelo específico sem
  confirmar que ele existe e está ativo — use `OPENROUTER_MODEL` como variável de
  ambiente com um valor padrão documentado no PR, não fixo no código sem explicação).
- **Zero Data Retention (ZDR):** o OpenRouter tem um filtro de roteamento que restringe a
  requisição só a provedores com política de não reter/treinar com o prompt — é pago
  (ainda que barato por token), diferente da faixa `:free`. Esta spec **não** implementa
  a troca automática — só documenta, no aviso da UI e num comentário no código, que essa
  opção existe e como ativá-la (parâmetro `provider.data_collection` ou `zdr: true` na
  chamada — **confirme o nome exato do parâmetro na documentação do OpenRouter na hora de
  implementar**, não invente o schema).

## Contrato obrigatório

### `services/assistente_ia.py` (novo módulo)

```python
def montar_contexto() -> dict:
    """Resumo agregado do estado da fazenda — só números já calculados, nada de
    tabela crua. É isto, e só isto, que sai para a API externa."""

def perguntar(pergunta: str, contexto: dict, *, api_key: str, modelo: str,
              timeout: int = 30) -> str:
    """Envia a pergunta + contexto ao OpenRouter, devolve a resposta em texto.

    Levanta AssistenteIndisponivelError em falha de rede, timeout, chave inválida
    ou limite de taxa (HTTP 429) — mensagem clara, sem vazar a chave no erro.
    """
```

- `montar_contexto()` retorna algo como: `{"rebanho": {...campos de AnimalStats...},
  "alertas_contagem": {"sumidos": N, "carencia": N, "prontos": N}, "recomendacoes":
  [...saída de recomendacoes.avaliar()...]}`. Sem UUID de animal, sem nome de
  fornecedor/comprador, sem valor monetário individual — só agregados (mesma disciplina
  da spec 0075/API dashboard).
- O prompt de sistema enviado ao modelo precisa deixar explícito: "Você responde só com
  base no contexto fornecido. Não invente dado que não está no contexto. Se a pergunta
  não puder ser respondida com o que foi dado, diga que não sabe — não adivinhe. Isto não
  é aconselhamento veterinário nem financeiro definitivo."

### `page_assistente` (nova, admin-only — mesmo padrão de `page_propriedades`/`page_regras`)

- Adicionar `("🤖","Assistente IA","assistente","")` à lista `pages` de admin em
  `_sidebar()`, e `"assistente": page_assistente` ao dicionário de dispatch em `main()`.
- Aviso permanente no topo da página (Regra de Ouro item 4).
- Campo de texto + botão "Perguntar". Sob demanda — não chama a API a cada rerun.
- Enquanto espera: `st.spinner`. Erro (`AssistenteIndisponivelError`): mensagem amigável,
  sem stack trace nem detalhe técnico da API pro usuário final.
- Resposta exibida com rótulo claro de que foi gerada por IA (Regra de Ouro item 5) — ex.
  `st.info` com um cabeçalho "🤖 Resposta gerada por IA" antes do texto.

## Critério de aceite

1. `montar_contexto()` testado — confirma que **nenhuma** chave de UUID de animal, nome
   de fornecedor/comprador ou valor monetário individual aparece no dicionário retornado
   (só agregados). Prova real, não revisão visual.
2. `perguntar()` testado com `requests.post` mockado: sucesso (resposta parseada
   corretamente), erro de rede, HTTP 429 (rate limit), chave ausente/inválida — todos
   levantam `AssistenteIndisponivelError` com mensagem em português, sem a chave de API
   no texto da exceção.
3. `OPENROUTER_API_KEY` ausente → `page_assistente` mostra "recurso não configurado", sem
   crash, sem chamar `perguntar()`.
4. Nenhum teste faz requisição de rede real ao OpenRouter — tudo mockado.
5. Aviso sobre nível gratuito/ZDR presente e visível no texto renderizado da página —
   teste com prova real (`AppTest`, mesmo padrão das specs 0079/0080/0082).
6. `grep -rn "sk-or-\|OPENROUTER_API_KEY\s*=\s*['\"]" services/ app.py` não encontra
   nenhuma chave hardcoded.
7. `flake8`/`ruff` e a suíte inteira verdes (`AGROTOP_FORCE_SQLITE=1 python -m unittest
   discover -s tests -t . -v`).

## Proibições

- ❌ Não dê ao assistente nenhuma função de escrita, direta ou indireta (nenhuma chamada
  a `add_*`/`update_*`/`register_*`/`atualizar`/`db.propriedades.atualizar` etc.) — é a
  proibição central desta spec.
- ❌ Não envie tabela crua (`animals`, `weighings`, `sales`, `medications`, `properties`)
  para a API externa — só os agregados definidos em `montar_contexto()`.
- ❌ Não hardcode a chave de API nem o nome do modelo sem documentar a fonte/data da
  verificação no PR.
- ❌ Não implemente memória de conversa entre perguntas nesta v1 — cada pergunta é
  isolada. Se quiser conversa contínua depois, é spec nova.
- ❌ Não implemente resumo de ficha de animal, resumo de lote/fazenda nem relatório
  narrativo automático nesta v1 — só a pergunta livre com o contexto agregado definido
  acima. São os outros modos do relatório estratégico (§6.3), ficam para depois.
- ❌ Não prometa, em nenhum texto da UI, que a resposta é aconselhamento profissional,
  veterinário ou financeiro definitivo — mesma disciplina de "não é certificação" já
  aplicada nas specs 0080/0082.
- ❌ Não construa um sistema de controle de cota/limite de taxa próprio — deixe o 429 do
  próprio OpenRouter propagar como `AssistenteIndisponivelError`, com mensagem amigável.
  Ele já limita por você; não duplique isso.
- ❌ Não adicione endpoint de API nem tela mobile para isto nesta v1 — mesma exclusão já
  aplicada a NDVI (0079), pacote de evidências (0080) e CAR (0082): ferramenta de mesa.

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t . -v
python -m compileall app.py services
grep -rn "sk-or-\|OPENROUTER_API_KEY\s*=\s*['\"]" services/ app.py   # confirme: nada
```

## Entrega

PR para `main`, pronto para revisão. Confirme no corpo do PR: qual modelo `:free` foi
usado e a data em que confirmou que ele existe no catálogo do OpenRouter, o texto exato
do aviso sobre nível gratuito/ZDR como aparece na UI, e que `montar_contexto()` não
inclui nenhum dado individualizável (cole a saída de um teste real).
