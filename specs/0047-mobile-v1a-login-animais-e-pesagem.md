# Spec 0047 — Mobile v1a: login, lista/ficha de animais e registrar pesagem (Flutter)

- **Tipo:** implementação · **Risco:** médio · **Esforço:** 4–6 dias
- **Branch:** `feat/mobile-v1a-login-animais-pesagem`
- **Crie:** `mobile/` (pasta nova, promovida a partir de `poc/mobile/`) — **não altere
  `poc/mobile/`, ele fica como está, intocado**

---

## Regra de ouro desta spec

**Contrato travado na spec [0044](0044-api-fastapi-autenticacao-e-endpoints-essenciais.md)
— não invente endpoint, payload nem formato de erro diferente do que ela define.** Isso é o
que permite esta spec rodar **em paralelo** com a 0044, sem esperar ela mesclar primeiro (ver
"Por que isto não precisa esperar a 0044", abaixo).

## Objetivo

Trilha 1 do [ROADMAP](../ROADMAP.md), etapa 2 — só a primeira fatia, não o escopo inteiro.
O ROADMAP pede "consulta e busca de animais, leitura de brinco, pesagem, movimentação entre
lotes, sanidade, consulta de carência, foto, confirmação de trato" — **esta spec entrega só
login + listar/ver animal + registrar pesagem**, porque é só isso que a 0044 expõe hoje.
Movimentação, sanidade, foto e trato esperam suas próprias specs de endpoint, cada uma
travando o contrato antes de existir tela para ela — mesmo padrão desta.

## Por que isto não precisa esperar a 0044

A 0044 já **define o contrato por escrito** (endpoints, payloads, formato de erro) — o que
faltava não era o contrato, era a implementação dos dois lados. Você implementa o lado
Flutter **contra esse contrato escrito**, testando com um **servidor mock local** que você
mesmo escreve (ver "Servidor mock para teste", abaixo) em vez da API real. Quando a 0044
mesclar, os dois lados batem — se não baterem, é porque um dos dois se desviou do contrato
escrito, e isso é bug, não coincidência de sequenciamento.

**Se você notar que precisa de um campo, endpoint ou comportamento que a 0044 não define,
NÃO invente um contrato novo por conta própria.** Pare, documente exatamente o que falta no
PR, e não implemente a tela que dependeria disso — é exatamente o tipo de divergência que
travar o contrato por escrito existe para evitar.

## Contexto que você precisa

`poc/mobile/` (PoC 0005, já entregue) já prova a arquitetura: três telas (login, animais
ativos, ficha), sem dado fictício, sem cálculo de GMD no Dart, erro de API sempre visível
— leia o README dela primeiro. **Diferente da maioria das PoCs deste projeto (R30), esta já
evita os atalhos que a regra existe para prevenir** (confirme lendo o código, não só o
README) — por isso você **promove** `poc/mobile/` para `mobile/` como ponto de partida
(`cp -r`, depois ajuste), em vez de reescrever do zero. Se encontrar algum atalho que o
README não confessa (dado mockado, senha fixa, TODO disfarçado de pronto), **pare e
reporte no PR em vez de propagar**.

O que muda em relação à PoC:
- Aponta para o contrato da **0044** (`/auth/login`, `/auth/refresh`, `/auth/logout`,
  `GET /animais`, `GET /animais/{id}`), não para `poc/api/`.
- Ganha a tela de **registrar pesagem** (`POST /animais/{id}/pesagens`), que a PoC não
  tinha.
- Ganha **refresh automático de token** (a PoC volta ao login na expiração; a 0044 tem
  refresh token, use-o).

⚠️ **Pegadinha ao promover a pasta:** `tool/generate_app_colors.py` calcula a raiz do
projeto por profundidade (`Path(__file__).resolve().parents[3]`), porque em
`poc/mobile/tool/` há exatamente três níveis até a raiz. Em `mobile/tool/` há só **dois**
— copiar sem ajustar faz o script apontar para fora do repositório. Ajuste o índice de
`parents[...]` depois de mover, e confirme rodando o script e checando que
`lib/app_colors.dart` saiu com valores reais de `ui/tema.py`, não um erro engolido.

## Contrato obrigatório

Não há assinatura de função Python aqui — o contrato é a **API HTTP da spec 0044**, ponto a
ponto. Telas obrigatórias:

1. **Login** — usuário/senha, erro de credencial inválida visível (nunca "carregando" preso).
2. **Lista de animais ativos** — busca por ID/brinco, paginação se a 0044 paginar.
3. **Ficha do animal** — dados que `GET /animais/{id}` devolver.
4. **Registrar pesagem** — peso, data, método; sucesso e erro visíveis; volta para a ficha
   atualizada.

Tema: **escuro, claro e "seguir o sistema"**, gerado de `ui/tema.py`
(`tool/generate_app_colors.py`, herdado da PoC) — nunca hex hardcoded (ROADMAP, Trilha 1,
"Design espelha o DESIGN.md").

## Servidor mock para teste

Escreva um mock HTTP mínimo (Python + `http.server`, ou um servidor Flutter/Dart de teste —
sua escolha) que implementa **exatamente** os payloads de request/response da 0044, para os
testes de integração do app rodarem sem depender da API real existir. Não precisa persistir
nada de verdade — pode devolver dados fixos coerentes com o contrato.

## Critério de aceite

1. `flutter analyze` limpo.
2. `flutter test` verde, incluindo um teste de fluxo completo (login → listar → abrir ficha
   → registrar pesagem → ficha reflete o novo peso) contra o **servidor mock**.
3. Token expirado dispara refresh automático **antes** de mostrar erro ao usuário — só cai
   para a tela de login se o refresh também falhar (refresh token revogado/expirado).
4. Erro de rede (servidor fora do ar) aparece como mensagem visível, nunca tela em branco
   ou "carregando" infinito.
5. `grep -rn "calculate_gmd\|regra de negócio\|fórmula" mobile/lib/` não acha nada — nenhum
   cálculo de negócio no Dart (ROADMAP, Trilha 1: "sem fórmula de GMD no Dart").
6. Testes visuais (golden, herdados da PoC) cobrem as quatro telas nos três temas.
7. `mobile/lib/app_colors.dart` bate, campo a campo, com a saída de
   `tool/generate_app_colors.py` rodado contra o `ui/tema.py` atual — prova de que não foi
   editado à mão.

## Proibições

- ❌ Não altere `poc/mobile/`, `poc/api/`, `app.py`, `database.py`, `services/`,
  `repositories/`, nem os arquivos da spec 0044.
- ❌ Não implemente movimentação, sanidade, foto, confirmação de trato ou leitura de
  brinco por câmera — fora do contrato da 0044, ficam para specs futuras.
- ❌ Não aponte para a API real nem tente subir `backend_api/` para testar — o mock é
  obrigatório justamente para não depender disso.
- ❌ Não invente campo, endpoint ou formato de erro que a 0044 não define. Diverge → pare
  e reporte, não implemente por cima de uma suposição.
- ❌ Não hospede nem publique em loja de aplicativos — decisão do mantenedor.
- ❌ Não adicione Bluetooth — etapa 4 da Trilha 1, precisa do equipamento físico.

## Como verificar antes de abrir o PR

```bash
cd mobile
flutter analyze
flutter test
python tool/generate_app_colors.py && git diff --stat lib/app_colors.dart   # deve ficar limpo
flutter build apk --debug
```

## Entrega

PR para `main`, pronto para revisão. No corpo, cole a saída dos comandos acima e diga
explicitamente: "testado contra servidor mock, não contra a 0044 real" — para o mantenedor
saber que a integração ponta a ponta com a API de verdade ainda precisa ser conferida depois
que as duas specs (0044 e esta) estiverem mescladas.
