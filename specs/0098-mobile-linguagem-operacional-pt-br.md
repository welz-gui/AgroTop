# Spec 0098 — Mobile: linguagem operacional e formatos pt-BR

- **Tipo:** manutenção · **Risco:** baixo · **Esforço:** 1 dia
- **Branch:** `fix/mobile-linguagem-operacional-pt-br`
- **Altere:** novo `mobile/lib/formatters.dart` e `mobile/lib/copy.dart`; os 10 arquivos de
  tela listados abaixo (só os trechos de texto/formatação citados); testes correspondentes
- **Pré-requisito:** nenhum

---

## Objetivo

Metade mobile do item RD03 da proposta de redesign
(`DESIGN-IS-2026-09-10/proposta-specs-redesign-para-revisao-claude.md`) — separada da metade
web ([spec 0099](0099-web-formatacao-pt-br.md)) porque são responsáveis e arquivos
completamente diferentes. **Achado ao investigar, maior que o citado na proposta original**:
a mensagem genérica de erro vaza o termo "API" em **10 arquivos**, não nos 6 citados — e só
**1 de 21** chamadas de `toStringAsFixed` no mobile converte ponto para vírgula (padrão
brasileiro).

## Contexto que você precisa

- **Mensagem "API indisponível" repetida ao pé da letra em 12 pontos, 10 arquivos**
  (confirme com `grep -rln "API indispon" mobile/lib/`):
  `alerts_page.dart`, `animals_page.dart`, `animal_photo_section.dart`,
  `create_lote_page.dart`, `csv_import_page.dart`, `dashboard_resumo_page.dart`,
  `devices_page.dart`, `feeding_page.dart` (3×), `login_page.dart`, `movement_page.dart`.
  Cada uma tem uma variação pequena do tipo `'API indisponível. <complemento>.'` — o usuário
  não sabe o que é "API".
- **Formatação decimal**: só `dashboard_resumo_page.dart` tem um helper privado (`_decimal`,
  linha ~409) que troca `.` por `,`. As outras 20 chamadas de `toStringAsFixed` no app
  (`grep -rn "toStringAsFixed" mobile/lib/`) mostram `382.4` em vez de `382,4`.
- **Nenhum pacote de data/locale** (`intl` etc.) está no `pubspec.yaml` — datas vindas da API
  em ISO (`2026-09-06`) provavelmente aparecem cruas onde exibidas; confira caso a caso, não
  presuma que todas precisam de reformatação (algumas podem já vir formatadas do backend).
- **Carência do animal** (`animals_page.dart:928-940`, corrigida pelo PR #391 para nunca
  afirmar liberação sem confirmar): texto atual "Sem restrição de carência" / "Animal
  liberado para comercialização/abate." — a proposta pede precisão maior: "Sem carência
  medicamentosa ativa" deixa claro **o que** foi verificado (só a carência por medicamento,
  não qualquer outra restrição possível).
- **Mensagem de operação salva offline** (`weighing_page.dart:114`, `medication_page.dart:181`,
  `movement_page.dart:142`): hoje "Salvo. Será enviado quando houver conexão." — já é preciso
  e correto; a proposta sugere "Salvo neste aparelho. Envio pendente." — troca de estilo, não
  correção de erro. Aplique por consistência entre as três telas, não é bug.

## Contrato obrigatório

1. **`mobile/lib/formatters.dart`** (novo): função `formatDecimalBr(double value, {int
   digits = 1})` — mesma lógica do `_decimal` já existente em `dashboard_resumo_page.dart`
   (extraia, não reescreva do zero). Substitua as 20 chamadas restantes de
   `toStringAsFixed` que exibem número ao usuário (não as que geram string para enviar à
   API — essas continuam com `.`).
2. **`mobile/lib/copy.dart`** (novo): constantes de mensagem reusadas, começando pela família
   "API indisponível" — nomeie por causa, não por tela, ex.:
   ```dart
   const kErroGenericoRede = 'Não foi possível conectar. Verifique sua internet e tente novamente.';
   String erroCarregamento(String recurso) => 'Não foi possível carregar $recurso. Tente novamente.';
   ```
   Troque as 12 ocorrências por chamadas a essas constantes/funções — nenhuma delas deve
   sobrar com a palavra "API" visível ao usuário.
3. **Carência**: troque "Sem restrição de carência" → "Sem carência medicamentosa ativa" e
   "Animal liberado para comercialização/abate." → mantenha, já está correto e claro.
4. **Offline**: as três `SnackBar` de "Salvo. Será enviado quando houver conexão." → "Salvo
   neste aparelho. Envio pendente."
5. **Erro específico de carência não verificada**: hoje, se `getAnimalMedications` falha, o
   `Future.wait([_detail, _medications])` da ficha (`animals_page.dart`) mostra o erro
   genérico de `AnimalDetail` quando é `_detail` que falha, mas quando é só `_medications`
   que falha a mensagem também vem genérica (`ErrorState` cobre os dois futures juntos, sem
   diferenciar qual falhou). **Não é obrigatório separar os dois futures nesta spec** — é uma
   mudança estrutural maior; se optar por não separar, documente no PR que a mensagem
   "Não foi possível verificar a carência" citada na proposta original fica para uma spec
   futura que trate os dois futures separadamente.

## Critério de aceite

1. `grep -rn "API" mobile/lib/screens/*.dart mobile/lib/*.dart` não encontra nenhuma
   ocorrência visível ao usuário (comentários de código não contam).
2. Todo número decimal exibido em tela usa vírgula (`382,4 kg`, não `382.4 kg`) — teste
   comparando `find.text` com a string exata, não `contains`.
3. Ficha do animal sem carência mostra "Sem carência medicamentosa ativa".
4. As três telas offline mostram "Salvo neste aparelho. Envio pendente."
5. Nenhum teste existente quebra por causa da mudança de string — atualize os que comparam
   a mensagem antiga literalmente.

## Proibições

- ❌ Não troque `toStringAsFixed` por `formatDecimalBr` em valores que vão para o corpo de
  uma requisição HTTP ou para o `OfflineQueue` — só o que é **exibido** ao usuário.
- ❌ Não introduza o pacote `intl` só para isto — os casos aqui não precisam de
  internacionalização completa, só ponto→vírgula.
- ❌ Não mude a lógica de carência corrigida pelo PR #391 — só o texto exibido.
- ❌ Não toque `backend_api/` nem `app.py` — metade web é a [spec 0099](0099-web-formatacao-pt-br.md).

## Como verificar antes de abrir o PR

```bash
cd mobile
flutter analyze
flutter test
grep -rn "API" lib/screens/*.dart lib/*.dart   # confirme: nenhuma ocorrência visível ao usuário
```

## Entrega

PR para `main`, pronto para revisão. Cole no corpo do PR a saída do `grep` de "API" mostrando
zero ocorrências restantes.
