# ADR 0005 — A fila de sincronização sai de `animal_events` e vira tabela própria

- **Status:** Aceito
- **Data:** 2026-08-04
- **Decisor:** proprietário do produto (welz-gui)
- **Complementa:** [ADR 0004](0004-conformidade-pnib.md) (etapa B2 — `animal_events`)
- **Base:** `requisitos_sistema_pnib_rs.md` v1.0, §6.2, §6.3, §10.2, §10.3, §10.4 e §14.1

---

## 1. Contexto

`animal_events.status_sincronizacao` nasce `'pendente'` e **não existe caminho para
mudá-la**. O `repositories/eventos.py` só oferece leitura (`pendentes_de_sincronizacao`),
e o gatilho append-only da etapa B2 (`trg_eventos_sem_update` no SQLite,
`fn_recusa_alteracao()` no Postgres) aborta qualquer `UPDATE` na tabela — inclusive o que
mudaria apenas essa coluna.

`identificador_oficial` tem o mesmo defeito e é pior: o §6.2 a descreve como
*"identificador retornado pelo sistema oficial"*, ou seja, ela **só pode** ser preenchida
depois do registro do evento. Nasce nula e assim fica.

**A consequência já é visível na tela.** `repositories/movimentacoes.py:pre_validar` conta
os eventos pendentes e `services/movimentacao.py` transforma o número no alerta
`sincronizacao_pendente`. Como o contador nunca zera, **toda** liberação de saída passa a
exigir justificativa (§8.4) por um alerta que não informa nada. O README já nomeia esse
defeito noutro contexto, a propósito do painel do §7.3: *"número que nunca zera ninguém
lê"*. Um alerta que sempre aparece deixa de ser alerta e vira ruído — e ruído em cima de um
campo de justificativa obrigatório ensina o operador a escrever qualquer coisa para
prosseguir, que é o oposto do que o §8.4 quer.

Descoberto em 2026-08-04 ao escrever `tests/ui_movimentacao_prova.py`, que precisou usar
`pre_validar` como oráculo — não conseguia fixar a lista de alertas esperados porque não
tinha como esvaziar a fila.

---

## 2. As duas opções

### Opção 1 — tabela de controle separada (`evento_sincronizacao`)

O estado de comunicação por evento sai de `animal_events` e vira registro próprio.
`animal_events` continua **estritamente imutável**: nenhum `UPDATE`, nenhuma exceção.

**O que o §6.3 diz a favor.** O parágrafo abre com

> "Eventos confirmados não devem ser apagados ou **sobrescritos**."

e, quando há erro, manda:

> "1. manter o evento original; 2. gerar evento de correção, cancelamento ou estorno;
> 3. registrar usuário, data, motivo e autorização".

Alterar `status_sincronizacao` no lugar é literalmente sobrescrever um evento confirmado, e
o remédio que o próprio parágrafo prescreve — **manter o original e acrescentar um registro
novo com usuário, data e motivo** — é a descrição exata desta opção.

**O que a reforça fora do §6.3.** O §10.2 é explícito:

> "Não integrar regras externas diretamente ao núcleo do sistema. Criar uma camada própria
> com: conectores por sistema, mapeamento de campos, [...] filas de envio, recebimento de
> retornos, tentativas automáticas, controle de indisponibilidade, idempotência,
> reconciliação, logs técnicos [...]"

A situação de sincronização **é** a camada de integração, e a norma manda mantê-la fora do
núcleo. Some-se a isso o §10.3, que não pede uma bandeira de dois valores e sim **catorze
situações** — de `em_fila` a `reconciliado_manualmente`, passando por `rejeitado` e
`erro_tecnico` —, e o §10.4, que enquanto não houver API oficial exige *"registro manual de
protocolo, anexação de comprovantes, **dupla conferência**, marcação como comunicado
externamente [e] posterior reconciliação"*. São ~6 colunas a mais, todas sobre o envio e
nenhuma sobre o fato ocorrido com o animal.

### Opção 2 — exceção no gatilho para `status_sincronizacao` e `identificador_oficial`

O gatilho passa a permitir `UPDATE` dessas duas colunas e continua recusando o resto.

**O que o §6.3 diz a favor.** A frase é sobre eventos **confirmados**, e o §6.2 lista
*"status da sincronização"* e *"identificador retornado pelo sistema oficial"* entre os
**dados comuns a todos os eventos** — a norma coloca as duas informações no evento, que é
por isso que as colunas existem. Reforça a leitura o item 5 do próprio §6.3:

> "5. sincronizar a correção com os sistemas externos, quando aplicável."

Sincronizar é ato **posterior** ao registro. Uma coluna que só pode ser preenchida depois
não descreve o fato: descreve o que se fez com ele. Sob essa leitura, "sobrescrever" um
evento significa alterar *o que aconteceu*, não anotar *que já foi comunicado*.

---

## 3. Decisão: opção 1

A leitura do §6.3 que sustenta a opção 2 é defensável, e não é por ela que a decisão se
resolve — é pelo que cada opção custa depois.

**1. A exceção não é escrevível com segurança no SQLite.** O SQLite não tem
`WHEN OLD.x IS DISTINCT FROM NEW.x` sobre um subconjunto arbitrário; o que existe é
`BEFORE UPDATE OF <colunas>`, que dispara quando as colunas listadas aparecem no `SET`.
Para permitir duas colunas seria preciso **listar as outras dezenove** — uma lista de
permissão por omissão. Toda coluna acrescentada a `animal_events` daqui em diante nasceria
**silenciosamente mutável** até alguém lembrar de incluí-la no gatilho. O ROADMAP tem a
lição escrita, e ela custou sete worktrees abandonados e duas specs feitas em dobro:
*"prefira mecanismo que torna o erro impossível a mecanismo que depende de alguém lembrar"*.
A opção 2 é exatamente a segunda categoria, no lugar mais sensível do sistema.

**2. A opção 2 perde a história.** `aguardando_envio → enviado → rejeitado → aceito` é uma
sequência em que cada passo sobrescreve o anterior. O §10.2 pede "tentativas automáticas" e
"logs técnicos"; o §14.1 pede saber quem mudou o quê. Com uma coluna só, a única resposta
possível é o estado final — e um evento rejeitado duas vezes fica indistinguível de um
aceito de primeira.

**3. A história teria de ir para outro lugar de qualquer jeito.** Registrar cada transição
em `audit_logs` seria obrigatório para atender ao §14.1. Ou seja: mesmo na opção 2, o
histórico de sincronização viveria fora de `animal_events`. Se ele vai viver fora, é melhor
que **seja** a fonte da verdade do que ser uma cópia paralela que pode divergir da coluna.

**4. Uma tabela de controle absorve o §10.3 e o §10.4 sem tocar em nada.** As catorze
situações, o protocolo manual, o comprovante e a dupla conferência entram como colunas
dela. Na opção 2, entrariam em `animal_events` — e cada uma dessas colunas teria de ser
acrescentada à lista de permissão do item 1.

### O que a decisão preserva

`animal_events` volta a ter uma regra só, sem asterisco: **nada nela muda, nunca**. Essa
frase é verificável por teste e é a coisa que a etapa B2 existe para poder afirmar.

### O que a decisão custa, e é assumido

- **Um `JOIN` a mais** em toda consulta de fila. Mitigado por índice; a fila é curta perto
  do histórico.
- **`animal_events.status_sincronizacao` e `identificador_oficial` viram vestígio.** Ficam
  no schema — o §6.2 as prevê, e removê-las seria migration destrutiva sem ganho. Passam a
  significar o **estado de nascimento** do evento, congelado, coerente com a linha ser
  imutável. `repositories/eventos.py` é o único leitor autorizado das duas, justamente para
  que ninguém consulte a coluna achando que ela responde "já foi comunicado?".
- **Duas fontes aparentes para a mesma pergunta.** É o risco real desta decisão. Mitigação:
  a coluna legada não entra em nenhum predicado novo, e o teste
  `test_coluna_legada_nao_responde_pela_fila` trava isso.

---

## 4. Forma da tabela

```
evento_sincronizacao
  id, evento_id → animal_events(id), sistema, situacao,
  protocolo, mensagem, observacoes, anexos, usuario, conferido_por,
  ocorrido_em, registrado_em, created_at
```

Decisões embutidas:

- **Também é append-only**, pelo mesmo gatilho (`fn_recusa_alteracao` no Postgres, dois
  gatilhos no SQLite). Uma tentativa de envio que aconteceu não desacontece. Assim o sistema
  inteiro tem uma regra só, e não "append-only aqui, mutável ali".
- **A situação vigente é a última linha** de cada par (evento, sistema). Nada de coluna
  "atual" que possa divergir do histórico.
- **`sistema` existe desde já** porque o §10.1 prevê vários destinos (Seapi/RS, SDA,
  Base Central, GTA, SISBOV) e o mesmo evento pode ir para mais de um. Enquanto não há API
  (§23), o valor padrão é `'oficial'` — nome deliberadamente neutro, para não presumir qual
  sistema será o primeiro.
- **`situacao` é validada** contra a lista do §10.3, que é fechada na norma. **`sistema`
  não é**, porque o §10.1 termina em "protocolos privados homologados" — lista aberta.
- **Um evento em aberto em qualquer sistema continua na fila.** Aceito num destino e
  rejeitado noutro é pendente.
- **Sem `tentativa`.** O §10.2 pede "tentativas automáticas", e a contagem sai de
  `COUNT(*) WHERE situacao='enviado'`. Coluna que se deriva é coluna que pode mentir.

### Por que a transição de sincronização não é ela própria um `animal_event`

O §6.1 lista *"sincronização com sistema oficial"* e *"rejeição pelo sistema oficial"* entre
os eventos mínimos, então a alternativa foi considerada: cada retorno do sistema oficial
viraria uma linha nova em `animal_events`, sem tabela nenhuma.

**Não funciona, e o motivo é circular:** todo `animal_event` nasce pendente de
sincronização. Um evento "sincronizado com o sistema oficial" nasceria ele próprio
aguardando comunicação, e a fila cresceria uma linha a cada vez que alguém tentasse
esvaziá-la. É o único desenho das três alternativas que **piora** o defeito que este ADR
existe para corrigir.

Os dois tipos do §6.1 continuam atendidos: a linha do tempo do animal os monta a partir de
`evento_sincronizacao`, que tem data, usuário e protocolo.

---

## 5. O que isto **não** resolve

O mecanismo existe; **a fila continua sem drenar sozinha**, e é preciso dizer isso com
todas as letras para não parecer que o alerta foi consertado.

- As APIs do §10.1 **não existem** (§23, e o ROADMAP marca "Integrações oficiais" como
  bloqueado). Nada envia nada automaticamente.
- Enquanto isso, o caminho previsto é o §10.4: lançar no portal oficial e **marcar como
  comunicado**, com protocolo e comprovante. Isso é `marcar_sincronizado()`, que existe —
  mas ainda **não tem tela**. Sem a tela, o operador não tem como usar, e o alerta de
  `sincronizacao_pendente` continua aparecendo em toda liberação.

Portanto, a próxima etapa (fora do escopo deste ADR) é a tela do §10.4, com dupla
conferência e anexo de comprovante. Ela é o que fecha a dívida nº 4 do ROADMAP de fato.

**Uma segunda melhoria, independente desta:** hoje o alerta conta os eventos pendentes do
**sistema inteiro**, e não os dos animais que estão saindo. O §8.3 pré-valida *aquela*
saída — contar a fila global faz um evento de pesagem de outro lote impedir uma liberação
limpa. Trocar o contador global por "pendências dos animais desta movimentação" mudaria
número de regra e precisa de decisão declarada (ROADMAP seção 3), então fica registrado
aqui e não foi feito junto.
