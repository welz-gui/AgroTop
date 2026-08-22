# Spec 0051 — Mobile: tela de sanidade (registrar medicamento e ver carência)

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** 2 dias
- **Branch:** `feat/mobile-sanidade`
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

**Contrato travado na spec [0050](0050-api-sanidade-medicamentos-e-carencia.md) — não
invente endpoint, payload nem formato de erro diferente do que ela define.** A 0050 já
está mesclada ([PR #181](https://github.com/welz-gui/AgroTop/pull/181)) — você pode testar
contra um servidor mock (mesmo padrão da 0047/0049) ou contra a API real, à sua escolha.

> ⚠️ **Atualização de 2026-08-22 — leia antes de começar.** Uma tentativa anterior desta
> spec parou corretamente ao notar uma contradição real: o item 2 abaixo pede
> preenchimento automático da dose ao escolher um protocolo, mas o contrato original de
> `GET /protocolos` não devolvia dose nenhuma — só `id`, `nome`, `via`, `carencia_dias`,
> `unidade_dose`. Implementar o preenchimento automático exigiria calcular a dose no Dart
> (fixa ou proporcional ao peso do animal, dependendo do protocolo), o que duplicaria uma
> fórmula de negócio no mobile — proibido (ver Proibições). **Corrigido:** `GET
> /protocolos` ganhou o parâmetro opcional `?animal_id=` e o campo `dose_sugerida`,
> calculados no servidor. O contrato abaixo já reflete a correção.

## Objetivo

Trilha 1 do [ROADMAP](../ROADMAP.md), subtarefas 1.8/1.9. Na ficha do animal (já existente,
da 0047), mostrar a carência ativa e permitir registrar aplicação de medicamento — a ação
de sanidade mais comum feita no curral.

## Contexto que você precisa

O app já tem, da 0047: login, lista de animais, ficha do animal, refresh automático de
token, tema gerado de `ui/tema.py`. Você adiciona uma seção/aba na ficha, não recria nada
disso.

## Contrato obrigatório

Contra a API da spec 0050:

```
GET  /protocolos?animal_id=<id-do-animal-da-ficha>
     -> lista de protocolos, cada um já com "dose_sugerida" calculada PARA ESTE ANIMAL
        (fixa ou proporcional ao peso corrente — a conta é do servidor, não do app;
        "dose_sugerida" pode vir `null` se o protocolo não tiver dose configurada)
GET  /animais/{id}/medicamentos          -> carência + histórico, ao abrir a ficha
POST /animais/{id}/medicamentos          -> registra aplicação
```

**Sempre passe `animal_id` ao chamar `GET /protocolos`** — é o que faz o servidor calcular
`dose_sugerida` para o animal certo. Chamar sem `animal_id` é válido (todo `dose_sugerida`
vem `null`), mas não serve pra este fluxo.

Telas/fluxos obrigatórios:

1. **Carência visível na ficha** — se `carencia_ate` não é nulo, um indicador visual claro
   (não só texto pequeno) mostrando até quando o animal está em carência. **Informação
   nunca depende só de cor** (ROADMAP R21) — ícone ou texto junto, nunca só uma faixa
   vermelha sem dizer o quê.
2. **Registrar aplicação** — formulário com: escolher um protocolo da lista (preenche
   medicamento/via/carência a partir dos campos do protocolo, e **dose a partir de
   `dose_sugerida`** — vindo pronto do servidor, nunca calculado no app — tudo editável)
   OU preencher manual; data (padrão hoje); confirmar chama `POST` e atualiza a carência
   mostrada na ficha sem precisar recarregar a tela inteira.
3. **Histórico de aplicações** — lista simples das aplicações anteriores (medicamento,
   dose, data), mais recente primeiro.

## Servidor mock para teste

Estenda o mock já usado pela 0047/0049, respondendo `GET /protocolos`,
`GET /animais/{id}/medicamentos` e `POST /animais/{id}/medicamentos` nos formatos exatos
da 0050.

## Critério de aceite

1. `flutter analyze` limpo.
2. `flutter test` verde, incluindo fluxo completo: abrir ficha → ver carência (ou "sem
   restrição") → escolher protocolo → confirmar → carência atualizada na tela (contra o
   mock).
3. Escolher um protocolo preenche via/carência a partir dos campos do protocolo e a
   **dose a partir de `dose_sugerida`** (chame `GET /protocolos?animal_id=<id-da-ficha>`,
   nunca calcule a dose no Dart) — e o operador consegue editar tudo antes de confirmar
   (não é campo travado).
4. Carência ativa é visível com ícone **e** texto, não só cor — teste que renderiza sem
   cor (ex.: modo alto contraste, se o Flutter test permitir) ainda comunica a informação
   pelo texto/ícone.
5. Testes visuais (golden) cobrem a seção de sanidade da ficha com e sem carência ativa,
   nos três temas.
6. `grep -rn "calculate_gmd\|regra de negócio\|fórmula\|dose_ref_kg\|dose_value" mobile/lib/`
   continua sem achar nada — a dose vem pronta de `dose_sugerida`, o app nunca vê
   `dose_ref_kg`/`dose_value` nem reproduz `dose_for_animal`.

## Proibições

- ❌ Não altere `backend_api/`, `poc/`, `app.py`, `database.py`, `services/`,
  `repositories/`, nem os arquivos das specs 0044/0047/0048/0049/0050.
- ❌ Não implemente cadastro de protocolo nem campanha em lote — a 0050 não expõe esses
  endpoints.
- ❌ Não invente campo, endpoint ou formato de erro que a 0050 não define. Diverge → pare
  e reporte.
- ❌ Não calcule dose no Dart em nenhuma circunstância — nem como "fallback" se
  `dose_sugerida` vier `null`. `null` significa "sem dose configurada nesse protocolo";
  mostre o campo vazio para o operador preencher, não invente um valor.

## Como verificar antes de abrir o PR

```bash
cd mobile
flutter analyze
flutter test
flutter build apk --debug
```

## Entrega

PR para `main`, pronto para revisão. Confirme no corpo que partiu de `origin/main` com a
0047 já mesclada, e diga se testou contra servidor mock ou contra a API real (0050 já está
em produção — as duas opções são válidas, só precisa ficar claro qual foi usada).
