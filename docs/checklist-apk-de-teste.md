# Checklist do APK de teste (aparelho real)

Preparado em 13/11/2026 a partir do que o app tem na `main` (`dd2e0f4`). O objetivo é ver **num aparelho** o que até
agora só foi visto em testes automáticos e com servidor falso. Tudo o que o app grava vai para o banco
**de produção** (veja o cuidado abaixo).

## 0. Antes de começar

**O APK que o CI gera sozinho não serve.** Em PR e push ele é construído com a URL de mentira
`https://api.example.invalid`. Só o disparo manual aceita a URL real. Para gerar o APK de verdade:

```bash
gh workflow run "Mobile CI (Flutter)" --ref main -f api_url=https://backend-api-463zq4f3da-uc.a.run.app
```

Quando terminar (uns 4 a 8 minutos), baixe o artefato `AgroTop-Mobile-APK`:

```bash
gh run download --name AgroTop-Mobile-APK --dir apk-teste
```

Use uma pasta **vazia**: se ela já tiver um `app-debug.apk` de um teste anterior, o download falha com "The file
exists" e o arquivo velho continua lá, parecendo o novo. Confira a data do arquivo depois de baixar. Para conferir
que a URL certa entrou, o log do passo "APK de depuração" deve mostrar
`Buildando com AGROTOP_API_URL=https://backend-api-463zq4f3da-uc.a.run.app`. O APK pesa uns 175 MiB (é de
depuração), então não passa por chat ou e-mail; use cabo USB, Drive ou o próprio GitHub. A pasta `apk-teste/` não
deve ser comitada: o arquivo passa de 100 MB e o GitHub recusaria o push.

É um APK de **depuração** (`app-debug.apk`, versão 0.1.0+1), assinado com a chave de depuração. No celular é preciso
permitir "instalar apps de fontes desconhecidas" para o app que você usar para abrir o arquivo.

> A URL acima é a da **API** (Cloud Run `backend-api`). A do app web (Streamlit, `agrotop-…run.app`) é outra; não
> use essa no APK.

**Cuidado com os dados.** Cada registro feito no teste vira evento de verdade na produção. Os eventos são
append-only: corrigir ou cancelar deixa o original e acrescenta o estorno. Por isso:

- [ ] Escolha **um ou dois animais só para o teste** e escreva `TESTE APK` nas observações de tudo o que registrar.
- [ ] Anote a hora em que começou o teste. Isso me deixa conferir no banco só o que for seu.
- [ ] Não vacine contra brucelose animais reais no item 7 (ele grava o estado do registro no SDA).

Anote o modelo do aparelho e a versão do Android: **não sei qual é o aparelho nem a versão mínima**, e isso nunca
foi testado.

## 1. Entrar e carregar

- [ ] Instalar e abrir sem travar. Pedir as permissões só quando a função for usada (câmera, localização).
- [ ] Entrar com seu usuário. A lista **Animais ativos** carrega.
- [ ] Fechar o app e abrir de novo: continua entrado, sem pedir senha.
- [ ] Menu: conferir que aparecem Resumo, Demarcar perímetro, Novo lote, Brincos e dispositivos, Estoque,
  Brucelose (SDA), Relatórios, Alertas operacionais, Trato do dia, Importar pesagens, Fila offline, Sair.
- [ ] Deixar o app parado uns 20 minutos e voltar: a **primeira chamada** pode demorar (o Cloud Run pode estar frio;
  vi 2 s hoje e já vi 12 s). Anotar quanto levou e se a tela deixa claro que está carregando. **O app não tem
  tempo-limite de rede configurado**; com sinal ruim, observar se a tela fica pendurada.

## 2. Piquete no histórico de aplicações (#697)

- [ ] Registrar um medicamento (data de hoje) num animal que está num piquete.
- [ ] Abrir a ficha do animal: na aplicação deve aparecer **"· Piquete: nome"**.
- [ ] Registrar outra aplicação com **data de alguns dias atrás**, depois de mover o animal para outro piquete:
  o histórico deve mostrar o piquete **daquela data**, não o de hoje.
- [ ] Aplicações anteriores à migration 0039 não mostram piquete (esperado).

## 3. Offline: o teste que importa

Este é o critério do piloto: registrar sem sinal, reconectar e não duplicar nada.

- [ ] Ligar o **modo avião**.
- [ ] Registrar, com datas de **2 a 3 dias atrás**: 2 pesagens, 1 medicamento e 1 movimentação de piquete.
- [ ] Abrir **Fila offline**: devem aparecer os 4 itens pendentes. Anotar o que a tela diz de cada um.
- [ ] **Fechar o app à força** e abrir de novo, ainda sem sinal: os 4 itens continuam na fila.
- [ ] Desligar o modo avião. Sincronizar (ou esperar). O **relatório de sincronização** deve listar 4 enviados.
- [ ] Conferir na ficha: cada registro aparece **uma vez**, com a data que você escolheu (não a de hoje).
- [ ] Repetir com **sinal que cai no meio**: ligar o avião logo depois de tocar em sincronizar. Depois reconectar e
  conferir que não há registro em dobro.

## 4. Aparelho e origem (#700) — eu confiro no banco

Depois do teste, me diga "terminei o teste do APK" com a hora em que começou. Eu leio no banco, **só leitura**:

- [ ] Todos os eventos do teste com `origem_informacao = app` (antes eram `web`).
- [ ] O mesmo `dispositivo` (um UUID) em todos eles.
- [ ] Datas de ocorrência as que você escolheu; data de registro a da sincronização.
- [ ] Nenhum evento repetido, e as chaves de idempotência `concluida`.
- [ ] Desinstalar e reinstalar o app, registrar uma pesagem: o `dispositivo` deve ser **outro** UUID.

## 5. Corrigir e cancelar pelo app

- [ ] Na ficha, usar **Corrigir ou cancelar** numa pesagem de teste e cancelar com motivo. Ela some das somas e o
  histórico fica com o estorno.
- [ ] Corrigir uma aplicação de teste (mudar a dose ou a data).
- [ ] Sem sinal, tentar cancelar: ver o que o app faz (não sei se a revisão entra na fila ou é recusada).

## 6. Câmera, QR e GPS

- [ ] **Ler QR do brinco**: pede a câmera, lê um QR de brinco e abre a ficha certa.
- [ ] Foto do animal: tirar e anexar, com sinal e sem sinal.
- [ ] **Demarcar perímetro**: pede localização, marca pontos ao ar livre. Em campo aberto e perto de árvore ou
  galpão, para ver a diferença de precisão.

## 7. Brucelose (SDA) — só com animais de teste

- [ ] Selecionar 2 animais de teste, **Vacinar contra brucelose**, sem sinal. Sincronizar depois.
- [ ] Conferir o estado do registro no SDA na ficha. Limite conhecido: o app **não baixa o estoque** ao vacinar.

## 8. Uso no curral (o que os testes não medem)

- [ ] Registrar uma pesagem do começo ao fim, de pé, com uma mão, e **cronometrar**.
- [ ] Ler a tela ao sol. Tema escuro e claro (o menu tem "Escuro", "Claro" e "Seguir o sistema").
- [ ] Os botões são tocáveis com a mão suja ou com luva? Algum texto pequeno demais?
- [ ] Qualquer mensagem de erro que você não entendeu: tirar print.

## Como me passar o resultado

Marque o que passou e o que falhou, com print das telas estranhas. Para cada falha, anote o que você fez, o que
esperava e o que viu. O que depender do banco eu confiro de leitura, sem alterar nada.

### Não verificado ainda (por isso este checklist)

- O app em qualquer aparelho real, contra a API de produção.
- O armazenamento seguro do Android falhando (o app segue sem o cabeçalho de aparelho, mas só foi simulado).
- Instalações antigas do app **não enviam** `X-Device-Id`: o campo fica vazio nelas.
- A tela de venda e o resto do app web não fazem parte deste teste.
