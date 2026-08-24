# Spec 0058 — Mobile: importação de pesagens por CSV

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 2–3 dias
- **Branch:** `feat/mobile-importacao-de-pesagens-csv`
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

**Contrato travado na spec [0057](0057-api-importacao-de-pesagens-csv.md) — não invente
endpoint, payload nem formato de erro diferente do que ela define.** Você não precisa
esperar a 0057 mesclar — teste contra um **servidor mock**, mesmo padrão da
0047/0049/0051/0053/0055.

## Objetivo

Trilha 1 do [ROADMAP](../ROADMAP.md), item 3 — importar um arquivo CSV exportado por um
indicador de balança direto do celular, sem digitar pesagem por pesagem. Vale mesmo depois
que houver Bluetooth (pareamento falha no campo).

## Contexto que você precisa

- **Não é por animal, é um arquivo com várias linhas de vários animais.** Igual à
  confirmação de trato (0055), é uma tela independente da ficha, com ponto de entrada
  próprio na navegação — não um botão dentro de `AnimalDetailPage`.
- **Ponto de entrada:** mais um ícone/ação em `AnimalsPage`, mesmo padrão dos pontos de
  entrada que as specs irmãs (0055 — trato, 0056 — leitura de QR) já adicionaram. Se ao
  pegar esta spec o `AppBar` já estiver com vários ícones empilhados, sinta-se livre para
  agrupar em um menu (`PopupMenuButton`) em vez de continuar empilhando `IconButton`s — o
  importante é que a ação continue acessível e tenha uma `Key` estável para teste, não a
  forma exata do widget.
- **Fluxo em duas chamadas ao MESMO endpoint, mesmo arquivo:** primeiro
  `confirmar=false` (só mostra prévia — nada grava), depois, só se o operador confirmar
  visualmente, `confirmar=true` (grava de verdade). **Não implemente uma segunda tela nem
  um segundo botão que pareça "confirmar de outro jeito"** — é reenviar o mesmo arquivo
  com o campo mudado.
- **Nenhum cálculo no app.** `alertas` (severidade alta) já vem pronto por linha aceita —
  não reimplemente `avaliar_pesagem` nem `parse_pesagens` em Dart. O app só lê o arquivo
  como bytes brutos e envia — a decodificação de encoding (`utf-8-sig`/`latin-1`) é
  responsabilidade do servidor, não do app.
- **Seleção de arquivo:** use um pacote de seleção de arquivo do ecossistema Flutter (ex.
  `file_picker`), filtrando por `.csv`/`.txt`. Dependência nova — documente no PR qual
  pacote escolheu.

## Contrato obrigatório

Contra a API da spec 0057:

```
POST /pesagens/importar-csv   (multipart: arquivo + confirmar)
     -> prévia (confirmar=false) ou gravação (confirmar=true) do mesmo arquivo
```

Telas/fluxos obrigatórios:

1. **Selecionar arquivo** (`.csv`/`.txt`) via seletor nativo.
2. **Prévia automática ao selecionar** — chama o endpoint com `confirmar=false` e mostra:
   contagem (total/aceitas/rejeitadas), tabela de rejeitadas com o motivo de cada uma,
   tabela de aceitas com o alerta em destaque quando houver (ícone **e** texto — nunca só
   cor, ROADMAP R21).
3. **Nada é gravado sem confirmação explícita** — um botão "Gravar N pesagem(ns)" separado,
   só habilitado depois da prévia carregar com sucesso e `aceitas` não vazio.
4. **Confirmar reenvia o mesmo arquivo com `confirmar=true`** e mostra o resultado final
   (`gravadas`), sem exigir selecionar o arquivo de novo.
5. **Erro de rede não perde o arquivo selecionado** — se a prévia ou a gravação falharem
   por rede, o operador pode tentar de novo sem precisar reselecionar o arquivo.
6. **Rejeitadas sempre visíveis quando existirem** — nunca escondidas atrás de um "ver
   mais" que o operador possa não notar; se há linha rejeitada, ela aparece na tela sem
   ação extra.

## Servidor mock para teste

Estenda o mock já usado pelas specs anteriores, respondendo `POST /pesagens/importar-csv`
nos formatos exatos da 0057 — inclua no mock pelo menos um cenário com linha aceita **e**
rejeitada **e** um alerta de severidade alta juntos, para provar que a tela mostra as três
coisas ao mesmo tempo sem esconder nenhuma.

## Critério de aceite

1. `flutter analyze` limpo.
2. `flutter test` verde, incluindo um fluxo completo: selecionar arquivo (simulado no
   teste) → prévia aparece com aceitas/rejeitadas/alertas → confirmar → resultado final
   com `gravadas` (contra o mock).
3. Teste prova que a prévia (`confirmar=false`) **não** aparece como já gravado na tela —
   o texto/estado antes de confirmar é claramente "pré-visualização", não "concluído".
4. Teste prova que confirmar reenvia o **mesmo** arquivo (mesmo conteúdo) com
   `confirmar=true` — não um payload reconstruído a partir da prévia.
5. Linha rejeitada aparece na tela com o motivo, no mesmo teste que tem linha aceita — as
   duas categorias visíveis ao mesmo tempo, nenhuma escondendo a outra.
6. Alerta de severidade alta numa linha aceita aparece com ícone **e** texto (não só cor).
7. Erro de rede simulado no mock mantém o arquivo selecionado disponível para tentar de
   novo, sem exigir reseleção.
8. `grep -rn "parse_pesagens\|avaliar_pesagem\|utf-8-sig\|latin-1\|regra de negócio\|fórmula" mobile/lib/`
   não acha nada — confirma que nenhuma lógica de parse/qualidade/encoding foi duplicada.

## Proibições

- ❌ Não altere `backend_api/`, `poc/`, `app.py`, `database.py`, `services/`,
  `repositories/`, nem os arquivos das specs anteriores.
- ❌ Não decodifique o conteúdo do arquivo no Dart (nem tente adivinhar o encoding) — envie
  os bytes brutos, o servidor decide.
- ❌ Não invente um jeito de excluir linhas individuais antes de confirmar — o fluxo é
  tudo-ou-nada, mesmo comportamento do botão único do web.
- ❌ Não invente campo, endpoint ou formato de erro que a 0057 não define. Diverge → pare
  e reporte.

## Como verificar antes de abrir o PR

```bash
cd mobile
flutter analyze
flutter test
flutter build apk --debug
```

## Entrega

PR para `main`, pronto para revisão. Confirme no corpo que partiu de `origin/main` com a
0047 já mesclada, qual pacote de seleção de arquivo você escolheu, e diga se testou contra
servidor mock ou contra a API real (0057).
