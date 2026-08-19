-- Índices de cobertura para chaves estrangeiras
-- (manutenção de performance — não ligada a nenhuma trilha do ROADMAP)
--
-- CONTEXTO
--   `mcp__supabase__get_advisors(type="performance")` no projeto AgroTop
--   (produção) aponta 25 chaves estrangeiras sem índice de cobertura, 28
--   índices nunca lidos por uma query real (`idx_scan = 0`) e 1 par de
--   índices idênticos. Investigado antes de decidir o que entra aqui:
--
--   1. FK sem índice — Postgres NÃO cria índice automático para o lado
--      "muitos" de uma FK (só para o lado referenciado, via PK/UNIQUE).
--      Sem índice, todo DELETE/UPDATE na tabela referenciada (ex.: apagar
--      um insumo) faz table scan em cada tabela filha para checar a
--      integridade referencial — e a maioria dessas FKs é exatamente o
--      padrão de JOIN mais comum do sistema (animal_uuid, insumo_id,
--      lote_id). As 25 desta seção foram conferidas uma a uma contra
--      `pg_indexes`: nenhuma tinha cobertura por coluna líder de outro
--      índice existente (ex.: `movimentacoes.propriedade_origem_id` JÁ
--      está coberta por `idx_mov_origem`, por isso não está nesta lista —
--      só as 3 outras FKs de `movimentacoes` entraram).
--
--   2. "Índice nunca usado" — o AgroTop de produção tem hoje ~14 animais e
--      populações do mesmo tamanho nas tabelas filhas. Abaixo de um
--      punhado de milhares de linhas, o planner do Postgres corretamente
--      prefere sequential scan a index scan — é MAIS RÁPIDO nessa escala,
--      então `idx_scan = 0` aqui não é "índice inútil", é "tabela pequena
--      demais para precisar dele ainda". Conferido um a um contra o código
--      (`repositories/`, `services/`): todos os 28 sustentam uma consulta
--      real e ativa (ex.: `idx_fixed_costs_lote` → centros de custo,
--      `idx_animals_status`/`idx_animals_lote` → praticamente todo filtro
--      de rebanho ativo do sistema). Nenhum candidato a DROP nesta
--      categoria — dropar por causa da leitura de hoje reintroduziria o
--      mesmo table scan que esta migration está corrigindo, assim que a
--      fazenda crescer (é literalmente o propósito do sistema: crescer).
--
--   3. Índice duplicado — `public.animals` tem `animals_pkey` E
--      `animals_uuid_key`, os dois `UNIQUE INDEX ... USING btree (uuid)`,
--      byte-idênticos (`pg_indexes` confere). Resíduo da migration que
--      promoveu `uuid` a chave primária (`animals_uuid_vira_pk`, ADR 0004).
--      **NÃO removido nesta migration** — tentativa real de `ALTER TABLE
--      animals DROP CONSTRAINT animals_uuid_key` (aplicada e revertida
--      atomicamente por erro, nenhum índice desta migration chegou a
--      ficar de pé) mostrou que 14 FKs de outras tabelas (`weighings`,
--      `medications`, `animal_costs`, `animal_movements`, `animal_photos`,
--      `deaths`, `sales`, `insumo_transactions`, `animal_events`,
--      `partos`, `animals.fk_animals_mae`, `animals.fk_animals_pai`,
--      `movimentacao_animais`, `dispositivos`) foram criadas amarradas ao
--      índice específico de `animals_uuid_key`, não "a qualquer índice
--      único na coluna" como o comentário original desta migration
--      assumia — Postgres liga cada FK ao índice que existia no momento em
--      que ela foi criada, e não a redireciona sozinho quando um
--      equivalente mais novo aparece. Removê-lo exigiria recriar as 14
--      constraints uma a uma para apontarem para `animals_pkey`; numa
--      tabela de ~14 linhas, o ganho (uma unique index a menos para
--      manter) não paga o risco de mexer em 14 FKs de uma vez só. Fica
--      registrado aqui para quem revisitar: não é um "esquecemos", é uma
--      troca de custo/benefício, e reavaliar exige o passo de recriação
--      das FKs, não só o DROP.
--
-- ADITIVA
--   Só cria índices — nenhuma tabela, coluna ou linha muda.
--
-- ROLLBACK
--   -- Derrubar qualquer índice individual não tem custo de integridade,
--   -- só volta a expor o table scan que ele evita:
--   DROP INDEX IF EXISTS idx_<nome>;

BEGIN;

-- ── CREATE INDEX: 25 chaves estrangeiras sem cobertura ──────────────────────

CREATE INDEX IF NOT EXISTS idx_animal_events_evento_anterior
    ON public.animal_events (evento_anterior_id);
    -- Autorreferência (correção de evento aponta pro evento original, §6.3);
    -- sem índice, resolver a cadeia de correções percorre a tabela inteira.

CREATE INDEX IF NOT EXISTS idx_animal_movements_animal_uuid
    ON public.animal_movements (animal_uuid);
    -- `get_movements(animal_id)` — histórico de piquete na ficha do animal.

CREATE INDEX IF NOT EXISTS idx_animals_fornecedor
    ON public.animals (fornecedor_id);
    -- Aba "🏆 Origem" (Financeiro) agrupa rentabilidade por fornecedor.

CREATE INDEX IF NOT EXISTS idx_animals_pai
    ON public.animals (pai_uuid);
    -- Genealogia paterna (spec de validação de genealogia).

CREATE INDEX IF NOT EXISTS idx_animals_prop_nascimento
    ON public.animals (propriedade_nascimento_id);
    -- Distingue propriedade de nascimento da propriedade atual (§3, PNIB).

CREATE INDEX IF NOT EXISTS idx_compra_itens_insumo
    ON public.compra_itens (insumo_id);
    -- Historico de compra por insumo (get_compra, listagens por item).

CREATE INDEX IF NOT EXISTS idx_compras_fornecedor
    ON public.compras (fornecedor_id);

CREATE INDEX IF NOT EXISTS idx_deaths_animal_uuid
    ON public.deaths (animal_uuid);

CREATE INDEX IF NOT EXISTS idx_dispositivos_propriedade_destino
    ON public.dispositivos (propriedade_destino_id);
    -- Estoque de brincos em trânsito entre propriedades (§5, PNIB).

CREATE INDEX IF NOT EXISTS idx_dispositivos_proprietario
    ON public.dispositivos (proprietario_id);

CREATE INDEX IF NOT EXISTS idx_feeding_checks_plan
    ON public.feeding_checks (plan_id);
    -- Checagens de trato por item do plano (Nutrição → Histórico de Checagens).

CREATE INDEX IF NOT EXISTS idx_feeding_plans_insumo
    ON public.feeding_plans (insumo_id);

CREATE INDEX IF NOT EXISTS idx_feeding_plans_lote
    ON public.feeding_plans (lote_id);
    -- `get_feeding_plans(lote_id=...)` — todo carregamento de dieta por piquete.

CREATE INDEX IF NOT EXISTS idx_health_protocols_insumo
    ON public.health_protocols (insumo_id);

CREATE INDEX IF NOT EXISTS idx_insumo_transactions_animal_uuid
    ON public.insumo_transactions (animal_uuid);

CREATE INDEX IF NOT EXISTS idx_insumo_transactions_compra
    ON public.insumo_transactions (compra_id);
    -- `get_insumo_compras` filtra por `compra_id IS NOT NULL/NULL`
    -- (compra com nota × entrada avulsa) — fluxo de caixa depende disso.

CREATE INDEX IF NOT EXISTS idx_insumo_transactions_insumo
    ON public.insumo_transactions (insumo_id);
    -- Ledger de estoque por insumo — base de `current_stock` reconstruível.

CREATE INDEX IF NOT EXISTS idx_lotes_property
    ON public.lotes (property_id);

CREATE INDEX IF NOT EXISTS idx_medications_insumo
    ON public.medications (insumo_id);

CREATE INDEX IF NOT EXISTS idx_movimentacoes_propriedade_destino
    ON public.movimentacoes (propriedade_destino_id);
    -- `propriedade_origem_id` já está coberta por `idx_mov_origem` — só o
    -- destino faltava.

CREATE INDEX IF NOT EXISTS idx_movimentacoes_titular_destino
    ON public.movimentacoes (titular_destino_id);

CREATE INDEX IF NOT EXISTS idx_movimentacoes_titular_origem
    ON public.movimentacoes (titular_origem_id);

CREATE INDEX IF NOT EXISTS idx_partos_propriedade
    ON public.partos (propriedade_id);

CREATE INDEX IF NOT EXISTS idx_produtores_organizacao
    ON public.produtores (organizacao_id);
    -- Hierarquia Organização → Produtor — toda navegação de titularidade
    -- (§3, §8 PNIB) sobe por aqui.

CREATE INDEX IF NOT EXISTS idx_sales_animal_uuid
    ON public.sales (animal_uuid);
    -- Rentabilidade por raça/origem já faz JOIN sales↔animals por uuid.

COMMIT;
