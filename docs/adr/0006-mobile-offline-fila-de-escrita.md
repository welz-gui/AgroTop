# ADR 0006 — Mobile offline: cache raso + fila burra + idempotência, sem merge automático

- **Status:** Aceito
- **Data:** 2026-08-24
- **Decisor:** proprietário do produto (welz-gui)
- **Relacionado:** [ADR 0002](0002-fronteira-de-portabilidade.md) (nenhuma lógica de
  negócio duplicada no mobile — R8), [ROADMAP](../../ROADMAP.md) Trilha 1, etapa 5
  ("Mobile v2 — offline + fila de sincronização")

---

## 1. Contexto

O Mobile v1 (specs 0044–0058) é inteiramente online — toda ação (pesagem, movimentação,
sanidade, foto, confirmação de trato) depende de resposta imediata da API. O ROADMAP
sempre tratou a etapa offline como a última de propósito: *"é a parte caríssima
(idempotência, conflitos, ordem de dependência) e não deve bloquear o resto"*.

Com as cinco fatias do Mobile v1 online concluídas (0044–0058) e o toolchain de
desenvolvimento mobile completo instalado localmente (Flutter + Android SDK + JDK,
2026-08-24), a etapa offline volta a ser uma candidata real — mas continua sendo decisão
de arquitetura, não tarefa mecânica de spec. Este ADR resolve essa decisão antes de
qualquer spec ser escrita.

**Necessidade real que motiva isto:** o operador no curral ou no pasto frequentemente não
tem sinal. Hoje ele não consegue registrar nada até recuperar conexão. O objetivo é deixar
a ação **enfileirada localmente** e sincronizada quando a conexão voltar — sem o operador
precisar lembrar de repetir a ação depois.

**Nota:** não confundir com a [ADR 0005](0005-fila-de-sincronizacao.md), que trata da fila
de comunicação de eventos regulatórios (PNIB) com sistemas oficiais (SISBOV/SEAPI) — tema
não relacionado, apesar do nome parecido.

---

## 2. Eixos de decisão e opções consideradas

### 2.1 O que fica disponível offline (leitura)

| Opção | Descrição | Custo |
|---|---|---|
| A — nada | Operador age às cegas (digita/escaneia o ID sem confirmar que existe) | Zero cache; erro só aparece na sincronização |
| **B — cache raso** ✅ | Última lista de animais/piquetes/protocolos baixada fica salva localmente, com "sincronizado às HH:MM" visível | Uma tabela local simples, sem histórico |
| C — réplica completa | Pesagens, medicamentos, fotos — tudo consultável offline | Exige endpoint novo ("mudanças desde X") por recurso, schema espelhado local |

### 2.2 Como a fila de ações pendentes é guardada e sincronizada

| Opção | Descrição | Robustez |
|---|---|---|
| **A — fila burra** ✅ | Uma tabela local (`sqflite`): tipo de ação + payload + `client_uuid` + `created_at`. Sincroniza em ordem de criação, um `POST` por vez, contra os **mesmos** endpoints que o app já usa online | Simples, replica exatamente o comportamento online, sem lógica nova no servidor além do dedupe (2.3) |
| B — fila com tela de pendências | Como A, mas com tela de revisão (editar/cancelar antes de enviar) e relatório final nas três categorias (sincronizado/pendente/erro — mesmo padrão já usado em movimentação e importação CSV) | Mais UX, mesmo mecanismo por baixo — **não descartada, só adiada** (ver §5) |

### 2.3 Idempotência

**Obrigatória, não opcional.** Sem isso, uma pesagem pode ser gravada duas vezes se a
conexão cair depois de o servidor gravar mas antes de o app receber a confirmação — cenário
comum em área de sinal instável, não uma hipótese rara.

**Mecanismo:** cada ação enfileirada carrega um `idempotency_key` (UUID v4 gerado no
momento em que a ação é enfileirada no aparelho, não no momento do envio). Os endpoints de
escrita relevantes (pesagem, medicamento, movimentação, trato, foto) passam a aceitar esse
campo e ignoram silenciosamente uma repetição da mesma chave — devolvendo o resultado já
gravado, não um erro nem uma segunda gravação.

### 2.4 Conflito — o que fazer quando o mundo mudou enquanto o app estava offline

Quase toda escrita deste app é **evento aditivo** (pesagem, medicamento, movimentação são
sempre `INSERT`, nunca edição de um registro existente — mesmo princípio já usado em
`animal_events`/ADR 0004). Isso elimina a maior parte do problema clássico de sincronização
offline: não existe "merge" de dois valores editados em paralelo, porque nada aqui é
editado, só acrescentado.

O que resta é o caso de a ação enfileirada **não fazer mais sentido** quando é reproduzida
— ex.: animal foi vendido por outra pessoa enquanto este aparelho estava offline, e agora
uma pesagem enfileirada para ele não deveria ser aplicada.

**Decisão: zero merge automático.** O servidor rejeita a ação com a mesma validação que já
usaria numa chamada online normal (nenhuma lógica nova). O app mostra o erro no relatório
de sincronização, e **o operador decide** o que fazer — sem tentativa de resolução
automática, sem heurística de "provavelmente é isso que a pessoa queria".

---

## 3. Decisão

**Cache raso (B) + fila burra (A) + idempotência obrigatória + zero merge automático.**

Motivo central: nenhuma das opções mais robustas (réplica completa, fila com revisão,
merge automático) tem, hoje, evidência de necessidade real — e cada uma delas custa caro
de um jeito que a ADR 0002 já rejeitou para outros contextos ("abstração especulativa
contra benefício hipotético"). A combinação escolhida cobre o cenário real descrito no
contexto (§1) por completo:

1. O operador vê o que foi carregado da última vez que teve sinal (cache raso resolve).
2. Ele consegue agir mesmo sem sinal, e a ação não se perde (fila burra resolve).
3. A ação não duplica se a sincronização falhar no meio (idempotência resolve).
4. Se algo mudou enquanto ele estava offline, ele fica sabendo e decide — em vez de o
   sistema "adivinhar" e potencialmente esconder um erro real (zero merge resolve, e evita
   o risco mais perigoso de todos: perda silenciosa de dado por auto-resolução errada).

Nenhuma lógica de negócio nova nasce no mobile — a fila só repete chamadas de API que o
app já faz online, e a validação de conflito continua inteiramente no servidor (R8/ADR 0002
seguidos à risca).

---

## 4. Forma técnica (mínima — orienta as specs, não as substitui)

```
-- tabela local (sqflite), no aparelho
fila_pendente
  id, client_uuid, endpoint, metodo, payload_json,
  criado_em, tentativas, ultimo_erro
```

- **`idempotency_key` = `client_uuid`** — reaproveita o mesmo UUID da fila, não precisa de
  campo extra.
- **Sincronização:** tentativa automática quando o app volta ao primeiro plano com conexão
  detectada, mais um botão manual "Sincronizar agora". **Sem serviço em segundo plano** —
  descartado de propósito: bateria e o SO matando processos em segundo plano no Android
  tornam um serviço confiável caro de manter para o ganho que dá (o operador volta a abrir
  o app ao ter sinal de novo de qualquer forma, no fluxo real de uso).
- **Cache raso:** tabela local com a última resposta de `GET /animais`, `GET /lotes`,
  `GET /protocolos` — sobrescrita a cada sincronização bem-sucedida, com timestamp visível
  na tela.

---

## 5. O que isto não resolve, e quando revisitar

- **Não dá para consultar histórico (pesagens, medicamentos anteriores) sem sinal** — só o
  necessário para localizar o animal e agir. **Revisitar réplica completa (opção C, §2.1)**
  se o uso real em campo mostrar que isso é necessidade recorrente, não conveniência.
- **A fila não tem tela de revisão antes de enviar** — toda ação enfileirada é enviada como
  foi criada. **Revisitar fila com tela de pendências (opção B, §2.2)** se o volume de ações
  por sincronização ou a taxa de erro mostrar que os operadores precisam corrigir antes de
  enviar, não só depois.
- **Não há retentativa infinita nem fila persistente entre reinstalações do app** — se o
  operador desinstalar o app com ações pendentes, elas se perdem. Aceito por ora; revisitar
  se isso acontecer na prática.

---

## Consequências

- **Duas specs decorrentes**, ainda não escritas:
  1. **API** — adiciona `idempotency_key` opcional aos endpoints de escrita existentes
     (pesagem, medicamento, movimentação, trato, foto), com dedupe. Mudança pequena e
     isolada, mesmo padrão de extensão que 0048/0050/0052/0054.
  2. **Mobile** — fila local (`sqflite`), cache raso de leitura, tela de sincronização com
     relatório de resultado. Escopo maior que as specs mobile anteriores, mas sem lógica de
     negócio nova.
- **Custo hoje:** nenhum — é só a decisão registrada. As specs entram na fila quando forem
  escritas.
- Nenhuma abstração especulativa adicionada (réplica completa, merge automático, serviço em
  segundo plano) — todas descartadas por falta de evidência de necessidade, não por serem
  difíceis.
