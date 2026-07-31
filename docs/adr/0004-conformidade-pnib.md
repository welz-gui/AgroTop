# ADR 0004 — Conformidade com o PNIB: chave surrogate, identificadores separados e hierarquia de propriedades

- **Status:** Aceito
- **Data:** 2026-07-31
- **Decisor:** proprietário do produto (welz-gui)
- **Substitui:** [ADR 0001](0001-multi-fazenda-schema-por-tenant.md) na parte de modelo de tenancy
- **Base:** `requisitos_sistema_pnib_rs.md` v1.0 (31/07/2026)

---

## 1. Contexto

O proprietário decidiu que o AgroTop deve ser **conforme ao PNIB** (Programa Nacional de
Identificação Individual de Bovinos e Bubalinos), e não apenas exportar dados para outro
sistema fazer a comunicação oficial.

Isso muda a natureza do produto: de ferramenta de gestão zootécnica e financeira para
**sistema de rastreabilidade individual com valor legal**. A sobreposição com o que existe
hoje é de aproximadamente 30 %.

### Prazos que tornam isso urgente

- adequação dos sistemas estaduais até **31/12/2026**;
- identificação obrigatória progressiva a partir de **2027**;
- vedação de movimentação de animais não identificados a partir de **01/01/2033**;
- o Rio Grande do Sul pode **antecipar** etapas.

### O que o schema atual impede

| Exigência | Situação hoje |
|---|---|
| §4.1 — identificador interno **imutável e separado** do brinco | ❌ `animals.id` **é** o número do brinco, e é PK de **7 FKs** |
| §4.2.3 — trocar brinco sem apagar o anterior | ❌ trocar o brinco = trocar a PK |
| §3.1 — hierarquia Organização → Produtor → **Propriedades** | ❌ não existe conceito de propriedade; `lote_id` é piquete |
| §8.1 — movimentação **entre propriedades** do mesmo titular | ❌ `animal_movements` é piquete→piquete, interno |
| §6.3 — eventos confirmados imutáveis, estado derivado deles | ❌ `status` e `current_weight` são mutados no lugar |
| §4.3 — mãe e pai | ❌ não existe genealogia |
| §14 — trilha de auditoria | ❌ não existe |
| §6.2 — data/hora do fato **e** do registro, com fuso | ❌ datas são `TEXT` `AAAA-MM-DD`, sem hora nem fuso |

---

## 2. Decisão

### 2.1 Chave surrogate imutável em `animals`

`animals` passa a ter **UUID interno imutável** como PK. O número do brinco vira **um
identificador entre vários**, não a identidade do registro.

É o pré-requisito de quase todo o resto: sem ele, não há como trocar brinco preservando
histórico (§4.2.3), nem ter dois animais com o mesmo número de manejo em propriedades
diferentes.

### 2.2 Tabela `animal_identifiers`

Identificadores deixam de ser colunas e viram registros com vigência:

```
animal_identifiers
  id, animal_uuid, tipo, valor, status,
  aplicado_em, removido_em, motivo_remocao, aplicado_por
```

`tipo` ∈ {`manejo`, `oficial_pnib`, `visual`, `rfid`, `sisbov`, `privado`}.

Regras (§4.2): um código oficial ou RFID não pode estar **ativo** em dois animais; remoção
não apaga o registro, apenas encerra a vigência. O formato do código oficial é
**configurável**, porque ainda não foi publicado (§23).

### 2.3 Tenancy: schema por **organização**, com `property_id` — substitui o ADR 0001

O ADR 0001 escolheu **schema por fazenda**, com dois argumentos que agora caem:

1. *"`animals.id` é o brinco e trocar a PK seria caro"* — a chave surrogate será feita de
   qualquer forma (2.1), então o obstáculo desaparece.
2. *"o comprador é o produtor de uma fazenda; não há painel consolidado"* — o PNIB exige
   hierarquia com **múltiplas propriedades por titular** (§3.1) e **movimentação entre
   propriedades do mesmo titular** (§8.1). Com schema por propriedade, essa movimentação
   vira transação entre schemas, sem integridade referencial.

**Novo modelo:** um schema por **organização**; dentro dele, `properties` como tabela e
`property_id` nas tabelas de negócio.

Isso preserva o que o ADR 0001 buscava — isolamento forte entre clientes (§15.2) — e
resolve o que ele não previa: movimentação entre propriedades do mesmo dono.

### 2.4 `animal_events` como espinha da rastreabilidade

Tabela **append-only**. Evento confirmado nunca é apagado nem sobrescrito; correção gera
evento de estorno com justificativa e autorização (§6.3).

Adoção **incremental**: primeiro os eventos passam a ser *registrados* junto das operações
atuais; só depois o estado do animal passa a ser *derivado* deles. Migrar as duas coisas de
uma vez seria reescrever o sistema inteiro num passo.

### 2.5 Eventos com data/hora e fuso — emenda à R5

A regra R5 do ROADMAP (datas como `TEXT` ISO) **continua valendo para datas de negócio**
(nascimento, pesagem, venda). Mas `animal_events` e `audit_logs` usam **`timestamptz`**,
com `ocorrido_em` e `registrado_em` separados (§6.2).

Motivo: em evento regulatório, o momento da comunicação tem valor jurídico, e a diferença
entre quando o fato aconteceu e quando foi registrado é auditável.

### 2.6 Perfis e permissões voltam ao escopo

O ADR 0001 cancelou `roles`/`permissions`. O §15.1 exige **11 perfis** com permissão por
organização **e por propriedade**. A decisão de cancelamento fica revogada.

O [ADR 0002](0002-fronteira-de-portabilidade.md) **permanece**: a identidade continua na
tabela `users` do próprio banco, Supabase Auth segue vetado. O §15.2 acrescenta exigência de
**2FA para perfis sensíveis**, que passa a ser requisito da implementação própria.

---

## 3. Caminho de migração

A migração toca **8 tabelas** com FK para `animals` — `weighings`, `medications`,
`animal_costs`, `animal_movements`, `animal_photos`, `sales`, `deaths`,
`insumo_transactions`.

Etapas, cada uma reversível:

1. **Adicionar** `animals.uuid` (gerado), sem remover nada. Sistema segue funcionando.
2. **Adicionar** `<tabela>.animal_uuid` nas 8 tabelas e popular a partir do `animal_id`.
3. **Criar** `animal_identifiers` e migrar o `animals.id` atual como identificador de tipo
   `manejo`, vigente.
4. **Trocar** as FKs para apontar ao `uuid`, mantendo `animal_id` como coluna legada.
5. **Reescrever** as consultas para usar o `uuid` — a camada `repositories/` da Fase A é o
   que torna isso viável em um lugar só.
6. **Remover** a coluna legada, apenas quando nada mais a referenciar.

**Pré-requisitos que já existem** e tornam isso seguro:
- backup completo com **restauração testada** (`tools/backup_banco.py` + `restaurar_banco.py`);
- baseline versionado e **replay validado** (`tools/testar_baseline.py`);
- **90 testes**, incluindo caracterização das regras de negócio — qualquer mudança de número
  aparece.

**Regra:** cada etapa é uma migration própria, com rollback documentado (R26), aplicada após
backup (R27).

---

## 4. Consequências

### Assumidas conscientemente

- **Esforço grande.** É um programa de meses, não um sprint. Vários módulos são novos:
  dispositivos (§5), nascimentos e genealogia (§7), movimentações entre propriedades (§8),
  camada de integração (§10), painel de conformidade (§16.3).
- **A Fase A vira ainda mais crítica.** A etapa 5 da migração depende de as consultas
  estarem concentradas em `repositories/`. Terminar o refactor deixa de ser higiene e passa
  a ser pré-requisito.
- **O roadmap se reordena.** Fazer Financeiro ou Nutrição antes da chave surrogate é
  construir sobre fundação que será trocada.
- **Nem tudo pode ser feito agora.** As APIs da Seapi/RS e da Base Central **não existem**;
  o próprio documento lista **19 pontos** ainda não confirmados (§23). Conector oficial hoje
  seria chute.

### Ganhos

- Rastreabilidade individual com valor legal amplia muito o mercado do produto.
- Auditoria e eventos imutáveis melhoram o sistema mesmo sem o PNIB.
- A hierarquia de propriedades era necessária de qualquer forma para comercializar.

---

## 5. O que fica configurável, e não no código

Por exigência do próprio documento (§2.1 e §11), **não** fixar em código:

- formato e quantidade de dígitos do código oficial;
- obrigatoriedade de RFID por categoria;
- prazos de aplicação e de comunicação;
- regras por UF, espécie, categoria, sexo, faixa etária e finalidade;
- níveis de bloqueio (informativo / alerta / bloqueio);
- layouts de integração.

Tudo com **vigência** (`data_inicial`, `data_final`) e **versão**, porque a regra que valia
em 2027 não é a que vale em 2030.

---

## 6. Alternativa recusada

**Ser apenas *integrável* ao PNIB** — exportar arquivo para outro sistema fazer a
comunicação oficial. Atenderia a obrigação legal com uma fração do esforço.

Recusada por decisão do proprietário em 2026-07-31: o objetivo é conformidade, não
interoperabilidade mínima.

*Registrado aqui porque, se o esforço se mostrar inviável adiante, esta é a saída de
emergência — e ela continua disponível.*

---

## 7. Pendente de regulamentação

Nada do que depende dos 19 itens do §23 deve ser construído antes da publicação oficial.
Em especial: formato do identificador, dispositivos homologados, layout e API da Seapi/RS,
autenticação, regras para animais de outros estados e necessidade de homologação de
softwares privados.

A arquitetura deve **estar pronta para recebê-los** — que é o objetivo deste ADR — sem
presumir qual será o conteúdo.
