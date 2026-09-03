# Spec 0072 — Mobile: recomendações do motor de regras na tela de alertas

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 1 dia
- **Branch:** `feat/mobile-recomendacoes`
- **Altere:** `mobile/` (a pasta que a spec 0047 criou) — só `alerts_page.dart`,
  `api_client.dart`, `models.dart` e os testes correspondentes
- **Pré-requisito obrigatório:** **a spec [0064](0064-mobile-tela-de-alertas-operacionais.md)
  precisa estar mesclada em `main`.** Confirme:
  ```bash
  git fetch origin
  git cat-file -e origin/main:mobile/lib/screens/alerts_page.dart 2>/dev/null \
    && echo "0064 já mesclada — pode seguir" \
    || echo "0064 AINDA NÃO mesclada — pare e avise quem te instruiu"
  ```

---

## Regra de ouro desta spec

**Contrato travado na spec [0071](0071-api-recomendacoes-motor-de-regras.md) — não invente
campo, regra nem severidade diferente do que ela define.** Você não precisa esperar a 0071
mesclar — teste contra um **servidor mock**, mesmo padrão da 0047/0049/.../0066. **Esta
spec só acrescenta uma seção à tela que a 0064 já entregou** (`alerts_page.dart`) — não cria
tela nova, não duplica as 5 seções que já existem lá.

A 0064 registrou explicitamente: *"'Recomendações' (motor de regras) não está nesta spec —
a 0063 não expõe isso, não invente uma seção pra ela."* Esta é essa spec.

## Objetivo

No web, `_alertas_operacionais` (aba "🔔 Operacionais") mostra **"🧭 Recomendações" antes**
das 5 categorias de alerta — cada recomendação com motivo e ação, coloridas por gravidade.
Esta spec traz a mesma seção para `AlertsPage` no mobile, contra a API da 0071.

## Contexto que você precisa

- **`mobile/lib/screens/alerts_page.dart`** já existe (spec 0064) — `_AlertsPageState`
  carrega `OperationalAlerts` via `widget.api.getOperationalAlerts()` e renderiza 5
  `_AlertSection`s dentro de um `RefreshIndicator`. Acrescente a busca de recomendações e
  uma sexta seção **antes das 5 existentes**, na mesma chamada de `_load()` (uma
  recomendação sem alerta nenhum ainda é útil sozinha, e vice-versa — carregar os dois em
  paralelo, não em série, com `Future.wait`).
- **Ordem de exibição por severidade** — `alta` primeiro, depois `media`, depois `baixa`
  (mesma ordem do web, `_GRAVIDADE_CARD`/`ordem` em `app.py::_alertas_operacionais`). A API
  da 0071 devolve a lista **sem ordenar** de propósito (decisão registrada na spec 0071) —
  **ordene no cliente**, é apresentação, não é reimplementar a regra que decide se algo
  dispara ou não.
- **Cor por severidade** — mesmo espírito do web (`card-red`/`card-yellow`/`card-green`):
  use `colorScheme.error`/algo próximo de amarelo/`colorScheme.primary` (ou os tons que já
  existem no tema do app — não invente cor nova, reaproveite o que `AppThemes` já define
  para estado de alerta/aviso/sucesso, mesmo padrão usado no restante do app mobile).
- **Cada recomendação mostra:** `titulo` em destaque, `motivo` abaixo, e `acao` (se
  presente) com um indicador visual diferenciado (ex. prefixo "👉", mesmo texto do web) —
  **não mostre o campo `dados`** (é formato livre, não tem rótulo definido para exibir ao
  operador; existe para quem for depurar, não para a tela).
- **Vazio:** nenhuma recomendação → mensagem de sucesso, mesmo padrão das 5 seções
  existentes (`"✅ Nenhuma recomendação no momento."`, mesmo texto do web).
- **`regra` é o identificador interno** (`"estoque_insuficiente"`, etc.) — **não mostre na
  tela**, é só para telemetria/depuração futura, não faz sentido para o operador.

## Contrato obrigatório

Contra a API da spec 0071:

```
GET /recomendacoes
  -> 200: [
       { "regra": str, "severidade": "alta"|"media"|"baixa", "titulo": str,
         "motivo": str, "dados": dict, "acao": str },
       ...
     ]
```

Ver a spec 0071 para os detalhes de cada campo. `dados` pode ter formato arbitrário —
decodifique como `Map<String, dynamic>` sem tentar tipar o conteúdo interno.

## Servidor mock para teste

Estenda o mock já usado pelas specs anteriores, respondendo `GET /recomendacoes` no
formato exato da 0071 — inclua ao menos um cenário vazio (lista `[]`, tela toda de sucesso)
e outro com recomendações nas três severidades (confirmando a ordenação alta→média→baixa
na tela, não na ordem em que o mock devolveu).

## Critério de aceite

1. `flutter analyze` limpo.
2. `flutter test` verde, incluindo: abrir a tela de alertas com mock devolvendo 3
   recomendações fora de ordem de severidade → aparecem na tela em ordem alta→média→baixa.
3. Lista vazia mostra a mensagem de sucesso, não uma seção vazia sem contexto (mesmo
   padrão das 5 seções já existentes).
4. `acao` ausente (`null`) numa recomendação não quebra a tela nem mostra "null" — só omite
   o indicador de ação para aquele item.
5. Pull-to-refresh (`RefreshIndicator` já existente) recarrega **tanto** os alertas quanto
   as recomendações — mock devolvendo cenários diferentes na segunda chamada, tela reflete
   os dois.
6. Falha ao carregar `GET /recomendacoes` (mock devolve erro) não impede as 5 seções de
   alerta de aparecerem, e vice-versa — as duas fontes falham de forma independente, mesmo
   espírito do botão de alertas na 0064 que não trava a lista de animais.
7. Testes visuais (golden) cobrem a seção de recomendações vazia e com itens nas três
   severidades, nos três temas. **Gere os PNGs de verdade** — `flutter test
   test/golden_screens_test.dart --update-goldens` — e **commite os `.png` resultantes em
   `mobile/test/goldens/`**. Se não tiver o toolchain Flutter disponível, **pare e reporte
   isso explicitamente antes de abrir o PR**, não abra alegando o critério cumprido sem os
   `.png` no diff.
8. `grep -rniE "estoque_insuficiente|piquete_acima_da_capacidade|carencia_impede_abate|gmd_abaixo_da_meta|margem_em_risco" mobile/lib/`
   só acha essas strings se forem os valores literais de `regra` vindos do JSON do mock nos
   testes — **não** acha lógica que decide se uma regra dispara. Toda decisão de "isto é
   uma recomendação válida" vem pronta do servidor.

## Proibições

- ❌ Não altere `backend_api/`, `app.py`, `database.py`, `services/`, `repositories/`, nem
  os arquivos das specs anteriores.
- ❌ Não crie uma tela nova — a seção entra em `AlertsPage`, existente desde a 0064.
- ❌ Não reimplemente nenhuma regra do motor (`estoque_insuficiente`,
  `piquete_acima_da_capacidade`, etc.) — o app só exibe o que a API já decidiu.
- ❌ Não mostre o campo `regra` nem `dados` na interface — são internos.
- ❌ Não invente ação de escrita nas recomendações (ex. "resolver", "marcar como visto") —
  a 0071 não expõe isso, é fora de escopo.

## Como verificar antes de abrir o PR

```bash
cd mobile
flutter analyze
flutter test
flutter build apk --debug
```

## Entrega

PR para `main`, pronto para revisão. Confirme no corpo que partiu de `origin/main` com a
0064 já mesclada, se testou contra servidor mock ou contra a API real (0071), e se os
golden PNGs foram gerados de verdade (cole a saída do `flutter test --update-goldens`).
