-- ADR 0004 · etapa B1.6 — remove `animal_id` das 8 tabelas filhas
--
-- CONTEXTO
--   Última etapa da migração de chave. As etapas 1 a 5 acrescentaram: uuid,
--   espelho nas filhas, tabela de identificadores, escritas preenchendo o uuid e
--   FKs apontando para `animals(uuid)`. Esta **remove** — e é a primeira cujo
--   rollback não é trivial.
--
-- ⚠️ POR QUE O ROLLBACK É DIFERENTE DAS OUTRAS
--   Todas as etapas anteriores se desfaziam com um `ALTER TABLE ... DROP`. Aqui
--   o dado da coluna vai embora. Reverter exige **restaurar backup**. O que
--   torna isso aceitável é que `animal_id` era redundante: o mesmo vínculo já
--   existe em `animal_uuid`, com FK ativa desde a etapa 5. Nada de informação se
--   perde — some uma segunda cópia da mesma ligação.
--
-- PRECONDIÇÃO (o bloco DO abaixo IMPÕE, não apenas verifica)
--   Nenhuma linha pode ter `animal_uuid` nulo enquanto `animal_id` estiver
--   preenchido. Se houver, a migração aborta antes de dropar qualquer coisa —
--   dropar nesse estado transformaria a linha em órfã silenciosa.
--
-- ROLLBACK
--   Não há rollback por DDL. Restaure o backup tomado imediatamente antes:
--     python tools/restaurar_banco.py backups/<arquivo>.zip
--   e confira as contagens por tabela antes de repontar a aplicação.

BEGIN;

-- ─── 1. Impõe a precondição ──────────────────────────────────────────────────
DO $$
DECLARE
    t            text;
    pendentes    bigint;
    total_ruim   bigint := 0;
BEGIN
    FOREACH t IN ARRAY ARRAY['weighings','medications','animal_costs',
                             'animal_movements','animal_photos','deaths',
                             'sales','insumo_transactions']
    LOOP
        EXECUTE format(
            'SELECT count(*) FROM %I WHERE animal_uuid IS NULL AND animal_id IS NOT NULL',
            t) INTO pendentes;
        IF pendentes > 0 THEN
            RAISE WARNING '%: % linha(s) com animal_id mas sem animal_uuid', t, pendentes;
            total_ruim := total_ruim + pendentes;
        END IF;
    END LOOP;

    IF total_ruim > 0 THEN
        RAISE EXCEPTION
            'Abortado: % linha(s) ficariam órfãs. Rode o backfill do animal_uuid antes.',
            total_ruim;
    END IF;
END $$;

-- ─── 2. Índices que ainda apontam para a coluna legada ───────────────────────
DROP INDEX IF EXISTS idx_weighings_animal_date;
DROP INDEX IF EXISTS idx_medications_animal;
DROP INDEX IF EXISTS idx_animal_costs_animal;
DROP INDEX IF EXISTS idx_animal_photos_animal;

CREATE INDEX IF NOT EXISTS idx_weighings_animal_date
    ON weighings USING btree (animal_uuid, weigh_date DESC);
CREATE INDEX IF NOT EXISTS idx_medications_animal
    ON medications USING btree (animal_uuid);
CREATE INDEX IF NOT EXISTS idx_animal_costs_animal
    ON animal_costs USING btree (animal_uuid);
CREATE INDEX IF NOT EXISTS idx_animal_photos_animal
    ON animal_photos USING btree (animal_uuid);

-- ─── 3. Remove a coluna legada ───────────────────────────────────────────────
-- O CASCADE derruba junto as FKs antigas em `animal_id`, criadas antes do ADR
-- 0004. As FKs para `animals(uuid)`, da etapa 5, não são afetadas.
ALTER TABLE weighings           DROP COLUMN IF EXISTS animal_id CASCADE;
ALTER TABLE medications         DROP COLUMN IF EXISTS animal_id CASCADE;
ALTER TABLE animal_costs        DROP COLUMN IF EXISTS animal_id CASCADE;
ALTER TABLE animal_movements    DROP COLUMN IF EXISTS animal_id CASCADE;
ALTER TABLE animal_photos       DROP COLUMN IF EXISTS animal_id CASCADE;
ALTER TABLE deaths              DROP COLUMN IF EXISTS animal_id CASCADE;
ALTER TABLE sales               DROP COLUMN IF EXISTS animal_id CASCADE;
ALTER TABLE insumo_transactions DROP COLUMN IF EXISTS animal_id CASCADE;

-- ─── 4. `animal_uuid` passa a ser obrigatório ────────────────────────────────
-- `insumo_transactions` fica de fora de propósito: nem toda saída de estoque é
-- de um animal (compra, ajuste, perda), e ali a coluna sempre foi anulável.
ALTER TABLE weighings        ALTER COLUMN animal_uuid SET NOT NULL;
ALTER TABLE medications      ALTER COLUMN animal_uuid SET NOT NULL;
ALTER TABLE animal_costs     ALTER COLUMN animal_uuid SET NOT NULL;
ALTER TABLE animal_movements ALTER COLUMN animal_uuid SET NOT NULL;
ALTER TABLE animal_photos    ALTER COLUMN animal_uuid SET NOT NULL;
ALTER TABLE deaths           ALTER COLUMN animal_uuid SET NOT NULL;
ALTER TABLE sales            ALTER COLUMN animal_uuid SET NOT NULL;

COMMIT;
