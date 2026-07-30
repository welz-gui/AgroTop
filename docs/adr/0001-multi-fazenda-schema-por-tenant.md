# ADR 0001 — Isolamento multi-fazenda: um schema por fazenda

- **Status:** Aceito
- **Data:** 2026-07-29
- **Decisores:** proprietário do produto (welz-gui)
- **Substitui:** a proposta de `farm_id` + tabelas `farms`/`farm_users`/`roles`/`permissions`/`role_permissions`
  da "Fase 0 — Fundação técnica" do `Plano_Implementacao_AgroTop_Web.md`

---

## Contexto

O AgroTop roda hoje em **uma única fazenda** (a do proprietário). Existe a intenção de,
caso o sistema tenha bom desempenho, **comercializá-lo para outros produtores**.

A dúvida era: implantar multi-tenancy agora (com `farm_id` em todas as tabelas) ou depois?
O receio era que converter o sistema mais tarde fosse mais caro.

Fatos levantados no código (2026-07-29):

| Fato | Evidência |
|---|---|
| `_conn()` é o **ponto único** de acesso ao banco | 82 usos; a conexão é criada em um só lugar (`database.py:80`) |
| O destino do banco já é configurável em runtime | `_database_url()` lê `DATABASE_URL` de env ou `st.secrets` |
| `animals.id` é o **número do brinco** e é PK | referenciado por **7 FKs** (`weighings`, `medications`, `animal_costs`, `sales`, `deaths`, `animal_photos`, `animal_movements`) |
| Escala atual | 12 animais ativos, 2 usuários |
| Cobertura de testes | 12 testes (auth + terminação) sobre 5.687 linhas |
| O schema está definido em **dois lugares** | 9 migrations no Supabase (só na nuvem) + `executescript` à mão em `database.py` |
| Essa duplicidade **já causou bug em produção/CI** | `protocol_id` e `lote_id` faltavam no DDL SQLite → `init_db()` quebrava em banco novo (corrigido em `75dce18`) |
| Já existe divergência não explicada | nuvem tem 22 tabelas, incluindo `profiles`, ausente no DDL local |

Pergunta que definiu a arquitetura: **quem é o comprador?**
Resposta: **o produtor de uma única fazenda** — cada cliente vê apenas os seus próprios dados.
Não existe requisito de painel consolidado entre fazendas.

---

## Decisão

Adotar **isolamento por schema (ou por projeto Supabase): uma fazenda = um schema**,
com o roteamento feito em `_conn()`.

**Não** adotar `farm_id` como coluna discriminadora em schema compartilhado.

### Por quê

1. **Elimina o problema caro.** Com schema por fazenda, cada uma tem sua própria tabela `animals`
   e o brinco volta a ser único naturalmente. Não é preciso trocar a PK nem mexer nas 7 FKs —
   que era o único retrofit genuinamente custoso.
2. **O ponto de inserção já existe.** `_conn()` concentra 100% do acesso ao banco. O roteamento por
   tenant é uma alteração localizada, não uma varredura por 82 call sites.
3. **A ordem inverte o custo.** Filtrar por `farm_id` hoje significa tocar em consultas espalhadas
   por 2.413 linhas de `database.py`, e refazer o trabalho depois da modularização em repositórios.
   Fazer o isolamento depois do refactor custa menos, não mais.
4. **Isolamento forte é argumento de venda.** "Os dados da sua fazenda ficam em base separada" é
   mais defensável que isolamento por cláusula `WHERE` — cuja falha é silenciosa e vaza dados.
5. **LGPD fica trivial.** Excluir ou exportar os dados de um cliente = dropar/dumpar o schema dele.
6. **`farm_id` não resolvia 80% do custo real** de comercializar: onboarding, convite de usuários,
   billing, backup por cliente, suporte. Nenhum deles fica mais barato por existir a coluna hoje.

---

## Consequências

### Pré-requisito load-bearing: migrations versionadas **no repositório**

A estratégia depende inteiramente de conseguir **recriar o schema do zero, de forma repetível**,
para cada nova fazenda. Hoje isso é impossível: as 9 migrations existem apenas na nuvem e o
schema é mantido à mão em dois lugares que já divergiram duas vezes.

Portanto:

1. Trazer as migrations para `supabase/migrations/` no repositório (versionadas em git).
2. Tornar o DDL SQLite **derivado** de uma única fonte de verdade — ou aceitar o SQLite apenas
   como ambiente de teste e gerar seu schema a partir das mesmas migrations. **Não** manter duas
   definições editadas à mão: essa foi a causa comprovada do bug `75dce18`.
3. Cada migration precisa ser idempotente e aplicável a um schema vazio.
4. Investigar a tabela órfã `profiles` na nuvem (provável resíduo do app mobile obsoleto,
   branch `feature/app-mobile`, arquivado) e removê-la ou documentá-la.

Sem isso, provisionar a fazenda nº 2 é um processo manual e sujeito a erro.

### O que **não** fazer agora

- Não adicionar `farm_id` a nenhuma tabela — nem às tabelas novas (agenda, compras, financeiro).
  Sob esta decisão, seria coluna morta.
- Não criar `farms`, `farm_users`, `roles`, `permissions`, `role_permissions`.
- Não construir seletor de propriedade na interface.
- Não criar os 7 perfis de acesso propostos. Manter `admin` / `operador` até existir demanda real.

### O que fazer quando o gatilho disparar

**Gatilho:** o segundo cliente pagante — ou o segundo "sim, eu compraria isso".

Sequência prevista:

1. Criar schema novo para o tenant e aplicar as migrations versionadas.
2. Rotear a conexão em `_conn()` por tenant (`SET search_path` para schema-per-tenant, ou
   `DATABASE_URL` distinta para projeto-per-tenant), resolvido a partir do login.
3. Onboarding, convite de usuários e billing — o trabalho real, independente desta decisão.

### Trade-offs aceitos conscientemente

| Custo aceito | Avaliação |
|---|---|
| Relatório consolidado entre fazendas fica difícil | Não é requisito: o comprador é o produtor de uma fazenda |
| Migrations precisam rodar em N schemas | Script simples, mas exige a disciplina do pré-requisito acima |
| Número de conexões cresce com os tenants | Aceitável com o pooler do Supabase para dezenas de fazendas |
| Acima de algumas centenas de tenants vira problema operacional | Nesse ponto haverá receita para re-arquitetar |

### Quando revisitar esta decisão

Se o perfil do comprador mudar para **gestor ou consultor que administra várias fazendas e quer
vê-las num painel único**, esta decisão passa a ser a errada: nesse cenário, `farm_id` em schema
compartilhado é o modelo correto — e aí será necessário resolver a colisão de PK do brinco
(chave surrogate em `animals` + as 7 FKs).

---

## Alternativas consideradas

**A. `farm_id` em schema compartilhado (proposta original do plano).**
Rejeitada: exige trocar a PK do brinco e as 7 FKs, espalha filtro por 82 call sites num monolito
que ainda vai ser refatorado, e o isolamento depende de nunca esquecer um `WHERE` — falha silenciosa.

**B. Não fazer nada e resolver 100% no futuro.**
Rejeitada como postura, embora próxima na prática: sem o pré-requisito de migrations no repositório,
provisionar o segundo cliente seria manual e frágil. A decisão aqui é registrar o caminho e
garantir o pré-requisito — não construir a funcionalidade.

**C. Um projeto Supabase por fazenda (em vez de schema).**
Mantida como variante válida da decisão. Isolamento ainda mais forte e `DATABASE_URL` distinta por
tenant (encaixe perfeito em `_database_url()`), ao custo de mais overhead operacional e de billing
por projeto. A escolha entre schema e projeto pode ser feita no momento do gatilho, sem impacto
no código escrito até lá.
