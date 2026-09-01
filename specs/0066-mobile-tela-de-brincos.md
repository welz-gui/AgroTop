# Spec 0066 — Mobile: tela de brincos e dispositivos

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 2 dias
- **Branch:** `feat/mobile-brincos`
- **Altere:** `mobile/` (a pasta que a spec 0047 criou)
- **Pré-requisito obrigatório:** **a spec [0047](0047-mobile-v1a-login-animais-e-pesagem.md)
  precisa estar mesclada em `main`.** Confirme:
  ```bash
  git fetch origin
  git cat-file -e origin/main:mobile/lib/app.dart 2>/dev/null \
    && echo "0047 já mesclada — pode seguir" \
    || echo "0047 AINDA NÃO mesclada — pare e avise quem te instruiu"
  ```

---

## Regra de ouro desta spec

**Contrato travado na spec [0065](0065-api-dispositivos-busca-e-mudanca-de-status.md) —
não invente endpoint, campo nem estado diferente do que ela define.** Você não precisa
esperar a 0065 mesclar — teste contra um **servidor mock**, mesmo padrão da
0047/0049/0051/0053/0055/0064. **Escopo é só busca + mudança de status** — as outras três
abas do `page_brincos` web (aplicar em animal, importar lote, importar arquivo) **não
entram**, ver "Proibições".

## Objetivo

Segundo item mobile do Tier 1 da [ADR 0007](../docs/adr/0007-escopo-de-paridade-admin-no-mobile.md).
No web, a aba "📋 Inventário" de `page_brincos` responde a pergunta de campo mais comum
sobre identificação: "esse brinco na minha mão — o que o sistema diz que ele é, e posso
mudar isso agora?" Esta spec traz essa resposta pro mobile, contra a API da 0065.

## Contexto que você precisa

- **Ponto de entrada:** um `IconButton` novo no `AppBar` de `AnimalsPage`, mesmo padrão dos
  botões de trato (0055) e alertas (0064) — ícone sugerido `Icons.sell_outlined` (ou
  `Icons.tag`), **sem badge** (não há uma "contagem" natural aqui, diferente de trato e
  alertas).
- **Um campo de busca por código** (`TextFormField`, teclado com maiúsculas automáticas,
  mesmo padrão de outros campos de código no app) + botão "Buscar" (ou busca ao submeter o
  teclado). Nenhuma lista é carregada de antemão — a tela nasce vazia, o operador digita o
  código que está lendo no brinco físico.
- **Dispositivo não encontrado:** mensagem clara ("Nenhum dispositivo ativo com esse
  código."), sem travar a tela — o operador pode buscar de novo.
- **Dispositivo encontrado:** mostra `codigo_visual`, tipo (traduza `tipo` com o mesmo
  dicionário fixo do web — ver "Rótulos fixos" abaixo), situação atual (rótulo em
  português) e, se houver, o lote. Abaixo, a lista de transições permitidas
  (`transicoes_permitidas` da resposta) como opções de mudança — se a lista vier vazia,
  mostre que a situação é definitiva ou bloqueada, não uma lista vazia sem contexto (mesmo
  princípio do critério 3 da 0064).
- **Transição que exige motivo:** mostra um campo de texto obrigatório antes de habilitar o
  botão de confirmar — mesmo padrão de `medication_page.dart`
  (`key: const ValueKey('medication-withdrawal-days')` como referência de estilo de form,
  não o campo em si).
- **Transição que exige autorização** (`exige_autorizacao: true`, hoje só
  `bloqueado_orgao → disponivel`): mostre a opção desabilitada com uma explicação curta
  ("Só o órgão libera") em vez de escondê-la — o operador precisa entender por que não pode
  fazer isso pelo app, não achar que a opção sumiu.
- **Rótulos fixos** — mesmo padrão da spec [0061](0061-mobile-metodo-de-pesagem-selecionavel.md)
  (`WEIGH_METHODS`): os 12 estados e seus rótulos em português vêm de `app.py::_ESTADO_BRINCO`
  (hardcode as mesmas 12 traduções no Dart, não invente rótulo diferente):
  ```python
  _ESTADO_BRINCO = {
      "solicitado": "Solicitado ao fornecedor", "recebido": "Recebido, a conferir",
      "disponivel": "Disponível", "reservado": "Reservado",
      "aplicado": "Aplicado em animal", "perdido": "Perdido",
      "danificado": "Danificado", "substituido": "Substituído",
      "inutilizado": "Inutilizado (definitivo)", "devolvido": "Devolvido (definitivo)",
      "cancelado": "Cancelado (definitivo)", "bloqueado_orgao": "Bloqueado pelo órgão",
  }
  _TIPO_BRINCO = {"brinco_visual": "Brinco visual", "boton": "Botton",
                  "conjunto": "Conjunto (visual + eletrônico)", "outro": "Outro"}
  ```

## Contrato obrigatório

Contra a API da spec 0065:

```
GET /dispositivos/{codigo_visual}
  -> { "id": str, "codigo_visual": str, "tipo": str, "status": str, "lote": str|null,
        "transicoes_permitidas": [{ "para": str, "exige_motivo": bool,
                                     "exige_autorizacao": bool }] }
  -> 404 se não encontrado

POST /dispositivos/{id}/status
  body: { "novo_status": str, "motivo": str|null }
  -> 200: { "ok": true, "de": str, "para": str }
  -> 400: transição recusada
```

Ver a spec 0065 para os detalhes de cada campo.

## Servidor mock para teste

Estenda o mock já usado pelas specs anteriores, respondendo `GET /dispositivos/{codigo}` e
`POST /dispositivos/{id}/status` no formato exato da 0065 — inclua cenários de: código não
encontrado (404), dispositivo em estado com múltiplas transições disponíveis, dispositivo
em estado terminal (sem transições), e ao menos uma transição que exige motivo.

## Critério de aceite

1. `flutter analyze` limpo.
2. `flutter test` verde, incluindo: buscar código inexistente → mensagem clara; buscar
   código existente → dados e situação aparecem; escolher uma transição sem motivo exigido
   → confirma e a tela reflete a nova situação; escolher uma transição com motivo exigido
   sem preencher → botão de confirmar desabilitado; preencher motivo → confirma.
3. Estado terminal (sem transições permitidas) mostra explicação, não lista vazia.
4. Transição que exige autorização aparece desabilitada com explicação, não escondida.
5. Testes visuais (golden) cobrem: busca vazia (tela inicial), código não encontrado,
   dispositivo encontrado com transições disponíveis, e o campo de motivo aberto — nos três
   temas. **Gere os PNGs de verdade** — `flutter test test/golden_screens_test.dart
   --update-goldens` — e **commite os `.png` resultantes em `mobile/test/goldens/`**. Um
   teste que só chama `expect(find.text(...))` sem `matchesGoldenFile` real não cumpre este
   critério (já custou uma rodada extra de revisão na 0051). Se não tiver o toolchain
   Flutter disponível, **pare e reporte isso explicitamente antes de abrir o PR**.
6. `grep -rn "solicitado.*recebido\|_PERMITIDAS\|_TERMINAIS" mobile/lib/` não acha a máquina
   de estados reimplementada — o app só usa `transicoes_permitidas` que o servidor devolve,
   nunca decide sozinho se uma transição é válida.

## Proibições

- ❌ Não altere `backend_api/`, `app.py`, `database.py`, `services/`, `repositories/`, nem
  os arquivos das specs anteriores.
- ❌ Não implemente "Aplicar em animal", "Importar lote" nem "Importar arquivo" — fora de
  escopo desta spec (ver Objetivo da 0065).
- ❌ Não reimplemente a máquina de estados do §5.2 no Dart — toda decisão de "essa
  transição é permitida?" vem de `transicoes_permitidas`, calculada no servidor.
- ❌ Não implemente autorização de órgão — mostre a opção desabilitada, não tente
  contorná-la.

## Como verificar antes de abrir o PR

```bash
cd mobile
flutter analyze
flutter test
flutter build apk --debug
```

## Entrega

PR para `main`, pronto para revisão. Confirme no corpo que partiu de `origin/main` com a
0047 já mesclada, se testou contra servidor mock ou contra a API real (0065), e se os
golden PNGs foram gerados de verdade (cole a saída do `flutter test --update-goldens`).
