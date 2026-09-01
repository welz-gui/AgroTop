# Spec 0065 — API: busca de dispositivo por código e mudança de status

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 1 dia
- **Branch:** `feat/api-dispositivos-status`
- **Altere:** só `backend_api/` (`main.py`, `schemas.py`) e os testes correspondentes
- **Pré-requisito:** nenhum — todas as funções que esta spec expõe já existem em
  `repositories/dispositivos.py` e `services/estados_dispositivo.py`, e já estão em
  produção via o app web.

---

## Regra de ouro desta spec

**Zero lógica nova.** Esta API só expõe, em JSON, o fluxo de "buscar brinco pelo código →
ver situação → mudar situação" que `app.py::_brincos_inventario` já faz chamando
`repositories/dispositivos.py` e `services/estados_dispositivo.py`. Nenhuma regra de
transição nova, nenhum estado novo — a máquina de estados do §5.2 já existe pronta e
testada (`services/estados_dispositivo.py`), esta spec só a traduz para JSON.

## Objetivo

Segundo item do Tier 1 da [ADR 0007](../docs/adr/0007-escopo-de-paridade-admin-no-mobile.md)
(paridade admin no mobile). No web, a aba "📋 Inventário" de `page_brincos` responde a
pergunta de campo mais comum sobre identificação: "esse brinco na minha mão — o que o
sistema diz que ele é, e posso mudar isso agora?" ("Reconciliar estoque de brinco é
conferência física — bate o número físico com o sistema ali na hora", ADR 0007 §2.2). Esta
spec cria a API; a spec mobile seguinte ([0066](0066-mobile-tela-de-brincos.md)) consome.

**Fora de escopo desta spec** (e da 0066): as outras três abas de `page_brincos`
("🏷️ Aplicar em animal", "📥 Importar lote", "📄 Importar arquivo") são operações em lote ou
de cadastro inicial — mais "mesa" que "celular na mão no curral", e não é o que a ADR 0007
justifica para esta fatia. Não invente endpoint para elas.

## Contexto que você precisa

- **Busca por código** — `repositories/dispositivos.py::por_codigo(codigo_visual: str) ->
  dict | None`. Devolve a linha inteira do dispositivo (`id`, `codigo_visual`, `tipo`,
  `tecnologia`, `fabricante`, `fornecedor`, `modelo`, `lote`, `data_aquisicao`,
  `proprietario_id`, `propriedade_destino_id`, `status`, `motivo_inutilizacao`,
  `data_baixa`, `divergencia`) ou `None` se não encontrado — **já filtra fora**
  `inutilizado`/`devolvido`/`cancelado` (mesma regra do web: "o número deles não volta ao
  estoque", não aparece na busca).
- **Transições permitidas a partir do estado atual** — não existe uma função pronta que já
  devolve a lista; `app.py` monta isso com uma list comprehension sobre
  `services/estados_dispositivo.py::estados()` chamando
  `transicao_permitida(atual, cada_estado)` para cada um. Repita exatamente essa lógica no
  endpoint (é orquestração de funções puras já existentes, não regra nova).
- **Mudar status** — `repositories/dispositivos.py::mudar_status(dispositivo_id: str,
  novo: str, *, motivo: str = "", usuario: str = "", tem_autorizacao: bool = False) ->
  dict`. Devolve `{"ok": True, "de": ..., "para": ..., "permitida": True, ...}` em sucesso,
  ou `{"ok": False, "erro": "..."}` / `{"ok": False, "de": ..., "para": ..., "permitida":
  False, "motivo": "..."}` em falha (dispositivo não encontrado, transição não permitida,
  motivo obrigatório ausente). **Repasse esse resultado como está** — não reformule as
  mensagens de erro.
- **`bloqueado_orgao` → `disponivel` exige autorização** (§14.2) — o parâmetro
  `tem_autorizacao` de `mudar_status` existe para isso. **Esta API não implementa
  autorização de órgão** (não há usuário "órgão" no sistema hoje) — sempre chame com
  `tem_autorizacao=False`. Se o dispositivo estiver `bloqueado_orgao`, a transição para
  `disponivel` vai aparecer nas `transicoes_permitidas` da consulta (porque
  `transicao_permitida` marca `exige_autorizacao=True`, não `permitida=False`) — o cliente
  mobile decide o que fazer com essa informação, não é problema desta API.
- **Doze estados fixos, doze rótulos fixos** — mesmo padrão da spec
  [0061](0061-mobile-metodo-de-pesagem-selecionavel.md) (`WEIGH_METHODS`): os nomes técnicos
  dos estados (`solicitado`, `recebido`, `disponivel`, ...) e a exigência de motivo por
  transição já vêm prontos do servidor. **Não crie endpoint para expor os rótulos em
  português** (`_ESTADO_BRINCO` em `app.py`) — são 12 valores fixos, a spec mobile
  seguinte hardcoda a tradução no Dart.

## Contrato obrigatório

```
GET /dispositivos/{codigo_visual}
  -> 200: {
       "id": str, "codigo_visual": str, "tipo": str, "status": str,
       "lote": str | null,
       "transicoes_permitidas": [
         { "para": str, "exige_motivo": bool, "exige_autorizacao": bool }
       ]
     }
  -> 404: dispositivo não encontrado (ou está inutilizado/devolvido/cancelado — mesma
     regra de `por_codigo`, não distinga os dois casos)

POST /dispositivos/{id}/status
  body: { "novo_status": str, "motivo": str | null }
  -> 200: { "ok": true, "de": str, "para": str }
  -> 400: transição recusada — corpo é o dict de erro de `mudar_status` tal como ele
     devolve (`ok: false`, mais `erro` ou `de`/`para`/`motivo` conforme o caso)
```

- Autenticação igual às outras rotas (token válido, qualquer papel — o web não restringe
  `page_brincos` a admin).
- `{id}` em `POST /dispositivos/{id}/status` é o `id` interno do dispositivo (o que
  `GET /dispositivos/{codigo_visual}` devolve em `id`), não o `codigo_visual`.
- **Sem `Idempotency-Key`** — mesmo padrão do endpoint `/trato/{plano_id}/confirmar`
  (spec 0054), que também não tem: fora do escopo da fila offline (ADR 0006 cobre só
  pesagem/medicamento/movimentação, spec 0060).

## Critério de aceite

1. `GET /dispositivos/{codigo}` sem token → 401.
2. `GET /dispositivos/{codigo}` com código inexistente → 404.
3. `GET /dispositivos/{codigo}` com dispositivo `inutilizado` → 404 (mesma regra de
   `por_codigo`, teste explicitamente este caso — não é o mesmo caminho que "não existe",
   mas o resultado observável é igual).
4. `GET /dispositivos/{codigo}` com dispositivo válido devolve os campos do contrato, e
   `transicoes_permitidas` bate com o que `services/estados_dispositivo.py` calcularia
   para aquele estado (teste com pelo menos dois estados de origem diferentes, ex.
   `disponivel` e `aplicado`, que têm listas de destino diferentes).
5. `POST /dispositivos/{id}/status` com transição permitida e sem motivo exigido → 200,
   dispositivo muda de fato (confirme consultando de novo).
6. `POST /dispositivos/{id}/status` para um estado que exige motivo, sem enviar motivo →
   400, dispositivo **não muda**.
7. `POST /dispositivos/{id}/status` para um estado que exige motivo, com motivo → 200,
   dispositivo muda e o motivo é gravado (confirme em `dispositivos.motivo_inutilizacao`
   quando o destino for `inutilizado`).
8. `POST /dispositivos/{id}/status` para uma transição não permitida (ex. `inutilizado` →
   `disponivel`) → 400, mensagem indica que o estado é definitivo.
9. `flake8`/`ruff` e a suíte inteira de `tests/test_backend_api.py` verde.

## Proibições

- ❌ Não implemente as abas "Aplicar em animal", "Importar lote" nem "Importar arquivo" de
  `page_brincos` — fora de escopo, ver "Objetivo".
- ❌ Não calcule nada no `backend_api/` — toda regra de transição já existe em
  `services/estados_dispositivo.py`; se uma transição parecer errada, o bug é na leitura
  do resultado, não em reimplementar a máquina de estados.
- ❌ Não implemente autorização de órgão (`tem_autorizacao=True`) — não há usuário "órgão"
  hoje, ver "Contexto".
- ❌ Não altere `app.py`, `database.py`, `repositories/dispositivos.py`,
  `services/estados_dispositivo.py` nem as specs anteriores.
- ❌ Não exponha os rótulos em português dos estados — são fixos, o mobile hardcoda.

## Como verificar antes de abrir o PR

```bash
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t . -v
python -m compileall backend_api tests
```

## Entrega

PR para `main`, pronto para revisão. Confirme no corpo que os 9 critérios têm teste com
prova real (não só "não deu erro") — mesmo padrão das specs 0054/0050/0063.
