# Spec 0060 — Mobile: fila offline e cache raso de leitura

- **Tipo:** implementação · **Risco:** médio · **Esforço:** 4–5 dias
- **Branch:** `feat/mobile-fila-offline`
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

**Implementa a [ADR 0006](../docs/adr/0006-mobile-offline-fila-de-escrita.md) — leia a ADR
inteira antes de começar, ela já resolveu as decisões de arquitetura.** Não reabra as
opções que a ADR descartou (réplica completa de leitura, fila com tela de revisão, merge
automático de conflito) — elas foram descartadas por falta de necessidade real comprovada,
não por serem difíceis. Esta spec implementa exatamente: **cache raso + fila burra +
`Idempotency-Key` + zero merge automático**, nada além disso.

**Contrato travado na spec [0059](0059-api-idempotency-key.md)** para o header
`Idempotency-Key` — não invente formato diferente. Você não precisa esperar a 0059
mesclar para testar contra mock, mas **o comportamento real de deduplicação só existe
depois dela mesclar** — sem ela, uma ação sincronizada duas vezes duplica de verdade no
servidor. Diga isso claramente no PR.

## Objetivo

Trilha 1 do [ROADMAP](../ROADMAP.md), etapa 5 — permitir registrar pesagem, medicamento e
movimentação **sem sinal**, sincronizando quando a conexão voltar.

## Escopo desta fatia (decisão registrada na ADR, não esquecimento)

- **Ações que entram na fila offline:** pesagem (`weighing_page.dart`), medicamento
  (`medication_page.dart`), movimentação (`movement_page.dart`). São as três telas de
  escrita mais usadas em campo e as mais simples de enfileirar (payload é só texto/número).
- **Foto FICA DE FORA desta fatia.** Enfileirar upload de imagem exige guardar os bytes
  localmente até sincronizar — complexidade real que não faz parte da ADR 0006 nem foi
  pedida. Continua exigindo conexão, como hoje.
- **Trato e importação CSV ficam de fora** — as specs 0054/0055/0057/0058 ainda não
  mescladas quando esta foi escrita; o mesmo padrão de fila pode ser estendido a elas numa
  spec futura, depois que existirem.
- **Cache raso cobre:** `GET /animais` (lista), `GET /animais/{id}` (ficha) e `GET /lotes`
  — o necessário para abrir a ficha de um animal específico e escolher destino de
  movimentação sem sinal. **`GET /protocolos` fica de fora** — offline, o formulário de
  sanidade permanece preenchível manualmente (o campo de dose sugerida fica vazio, mesmo
  comportamento já previsto na spec 0051 para quando o protocolo não tem dose configurada).

## Contexto que você precisa

- **Duas responsabilidades, dois mecanismos separados** (não misture num só):
  1. **Fila de escrita** (`sqflite`, dependência nova — banco relacional local, porque
     precisa de status por item e ordem de processamento).
  2. **Cache raso de leitura** (`shared_preferences`, já é dependência do projeto — só
     guarda o último JSON de cada endpoint como string, mais um timestamp; não precisa de
     banco relacional porque não há consulta, só "qual foi a última resposta boa").
- **Como distinguir "sem sinal" de "erro real do servidor"** — o app já faz essa distinção
  hoje, em `AnimalsPage._load`: um `catch (ApiException e)` é resposta HTTP real do
  servidor (404, 422, etc. — **não enfileire, mostre o erro**); um `catch (_)` genérico é
  falha de rede (`SocketException`, timeout — **enfileire**). Use exatamente esse critério
  nas três telas de escrita.
- **`client_uuid`** gerado no momento em que a ação entra na fila (não no momento do
  envio) — usa como `Idempotency-Key` no cabeçalho da chamada, contrato da 0059. Precisa de
  um gerador de UUID — pacote `uuid` (novo, pequeno, sem código nativo) é a escolha óbvia.
- **Estrutura da fila** (mesma da ADR 0006, seção 4):
  ```
  fila_pendente
    id, client_uuid, endpoint, metodo, payload_json,
    criado_em, tentativas, ultimo_erro
  ```
  `endpoint`/`metodo`/`payload_json` guardam o suficiente para reconstruir a chamada
  exata que `ApiClient` faria — não reimplemente a lógica de cada endpoint na hora de
  sincronizar, **chame os mesmos métodos de `ApiClient`** (`registerWeighing`,
  `registerMedication`, `moveAnimals`) passando o `Idempotency-Key`. Isso também significa
  que `ApiClient` precisa aceitar um `idempotencyKey` opcional nesses três métodos.
- **Sincronização automática:** ao app voltar ao primeiro plano
  (`WidgetsBindingObserver.didChangeAppLifecycleState` → `AppLifecycleState.resumed`),
  tenta processar a fila em ordem de criação. **Sem `connectivity_plus` nem serviço em
  segundo plano** (decisão da ADR) — a tentativa em si já revela se há conexão: sucesso
  remove da fila, falha de rede para o processamento inteiro (não adianta tentar os
  próximos se o primeiro já falhou por falta de sinal).
- **Botão manual "Sincronizar agora"** faz a mesma coisa sob demanda.
- **Item rejeitado pelo servidor** (`ApiException` com `statusCode` real durante a
  sincronização, não falha de rede) **sai da fila automaticamente** — não fica tentando
  para sempre — e aparece no relatório de sincronização como rejeitado, com o motivo.
  **Zero tentativa de resolver sozinho** (ADR 0006) — o operador decide manualmente
  (registrar de novo com dados corrigidos, se fizer sentido, ou descartar).

## Contrato obrigatório

Sem endpoint novo além do que a 0059 já define (o header `Idempotency-Key`). Reaproveita
`registerWeighing`, `registerMedication`, `moveAnimals`, `listAnimals`, `getAnimal`,
`listLotes` — todos já existentes em `ApiClient`.

Telas/fluxos obrigatórios:

1. **Ação enfileirada quando a rede falha** (não quando o servidor responde com erro) —
   confirmação visível ("Salvo. Será enviado quando houver conexão."), nunca um erro que
   pareça que a ação se perdeu.
2. **Indicador de pendências** em `AnimalsPage` — contagem visível de itens na fila
   (mesmo espírito do badge de trato já usado no web, mas aqui é a fila offline).
3. **Cache raso na lista e na ficha** — se `GET /animais`/`GET /animais/{id}`/`GET /lotes`
   falhar por rede e existir cache local, mostra o cache **com aviso visível** ("dados de
   HH:MM, pode estar desatualizado" — ícone **e** texto, nunca só uma cor, ROADMAP R21).
   Sem cache e sem rede, mostra o erro normal (não há o que exibir).
4. **Sincronização automática ao voltar ao app**, mais botão manual.
5. **Relatório de sincronização com três categorias sempre visíveis** — sincronizado com
   sucesso / ainda pendente (falha de rede, tenta de novo depois) / rejeitado pelo servidor
   (com o motivo) — mesmo padrão já usado em movimentação (spec 0049) e importação CSV
   (spec 0058): nenhuma categoria escondida, mesmo vazia.

## Servidor mock para teste

Estenda o mock já usado pelas specs anteriores. Para testar a dedução de rede vs. erro de
servidor, o mock precisa conseguir simular os dois: um `MockClient` que lança uma exceção
de rede pura (não uma resposta HTTP) para alguns casos, e devolve uma resposta HTTP de erro
normal (ex. `404`) para outros. Para a deduplicação por `Idempotency-Key`, o mock deve
guardar a última chave vista por endpoint e devolver a mesma resposta se receber a mesma
chave de novo — replicando o comportamento real da 0059, mesmo sem ela estar mesclada.

## Critério de aceite

1. `flutter analyze` limpo.
2. `flutter test` verde, incluindo um fluxo completo: simular falha de rede ao registrar
   uma pesagem → ação enfileirada, confirmação mostrada, sem erro → simular volta da
   conexão (app para primeiro plano, ou botão manual) → sincroniza → item some da fila,
   relatório mostra "sincronizado".
3. Teste prova que uma ação que falha por **erro real do servidor** (não rede) — ex. mock
   devolvendo `404` — **não** é enfileirada, aparece como erro imediato na tela.
4. Teste prova que um item da fila, ao sincronizar, envia o `Idempotency-Key` — inspecione
   a chamada no mock e confirme o header presente com o `client_uuid` da ação.
5. Teste prova que um item que é **rejeitado durante a sincronização** (mock devolve erro
   real, não falha de rede) sai da fila e aparece no relatório como rejeitado — não fica
   preso tentando de novo.
6. Teste prova o cache raso: com uma resposta cacheada de `GET /animais` e o mock
   simulando falha de rede na tentativa seguinte, a lista mostra os dados cacheados com o
   aviso de desatualização visível (ícone e texto).
7. Testes visuais (golden) cobrem: indicador de pendências com fila vazia e com itens, e a
   tela/banner de dados cacheados desatualizados, nos três temas. **Gere os PNGs de
   verdade** (`CAPTURE_GOLDENS=1 flutter test --update-goldens`) — se você não tiver
   Flutter disponível, pare e reporte isso explicitamente, não abra a PR alegando o
   critério cumprido sem os arquivos `.png` no diff (mesma lição da spec 0051/0055).
8. `grep -rn "regra de negócio\|fórmula" mobile/lib/` continua sem achar nada — a fila só
   repete chamadas de API já existentes, nenhum cálculo novo.

## Proibições

- ❌ Não altere `backend_api/`, `poc/`, `app.py`, `database.py`, `services/`,
  `repositories/`, nem os arquivos das specs anteriores.
- ❌ Não implemente fila para foto, trato ou importação CSV — ver "Escopo desta fatia".
- ❌ Não implemente resolução automática de conflito — todo item rejeitado pelo servidor
  vira decisão do operador, nunca automática (ADR 0006).
- ❌ Não adicione `connectivity_plus` nem um serviço em segundo plano — a ADR descartou os
  dois de propósito.
- ❌ Não invente um segundo mecanismo de fila além de `sqflite` + os métodos que já
  existem em `ApiClient` — não reimplemente a lógica de pesagem/medicamento/movimentação.
- ❌ Não persista dados sensíveis (token) na fila local — a fila guarda payload de
  domínio, não credenciais; o token continua só no `TokenStore` seguro que já existe.

## Como verificar antes de abrir o PR

```bash
cd mobile
flutter analyze
flutter test
flutter build apk --debug
```

## Entrega

PR para `main`, pronto para revisão. Confirme no corpo que partiu de `origin/main` com a
0047 já mesclada, se a 0059 já estava mesclada quando você testou (e se não, que testou a
deduplicação só contra o mock), e se os golden PNGs foram gerados de verdade.
