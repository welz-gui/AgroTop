-- ADR 0004 · etapa B1.2 — espelhar `animals.uuid` nas 8 tabelas filhas
--
-- CONTEXTO
--   Segunda das seis etapas. Continua **aditiva**: acrescenta a coluna e a
--   preenche. Nenhuma FK muda — `animal_id` segue sendo a referência real, e as
--   duas colunas convivem. É o que torna esta etapa reversível.
--
--   A troca das FKs é a etapa 4, e só acontece depois que o espelho estiver
--   completo e conferido.
--
-- VERIFICADO ANTES DE APLICAR (2026-07-31)
--   backup completo conferido: backups/agrotop_20260731_210351.zip
--
-- VERIFICADO DEPOIS
--   weighings 42/42 · medications 24/24 · animal_costs 28/28
--   animal_movements 14/14 · animal_photos, deaths, sales 0/0
--   insumo_transactions: 2 linhas sem espelho, corretamente — são `compra` e
--   `trato_lote`, que não têm animal vinculado (animal_id NULL).
--   Pendentes (animal_id preenchido e uuid nulo): ZERO nas 8 tabelas.
--
-- ROLLBACK
--   ALTER TABLE weighings           DROP COLUMN animal_uuid;
--   ALTER TABLE medications         DROP COLUMN animal_uuid;
--   ALTER TABLE animal_costs        DROP COLUMN animal_uuid;
--   ALTER TABLE animal_movements    DROP COLUMN animal_uuid;
--   ALTER TABLE animal_photos       DROP COLUMN animal_uuid;
--   ALTER TABLE deaths              DROP COLUMN animal_uuid;
--   ALTER TABLE sales               DROP COLUMN animal_uuid;
--   ALTER TABLE insumo_transactions DROP COLUMN animal_uuid;
--   (seguro: nada referencia essas colunas ainda)

ALTER TABLE weighings           ADD COLUMN IF NOT EXISTS animal_uuid TEXT;
ALTER TABLE medications         ADD COLUMN IF NOT EXISTS animal_uuid TEXT;
ALTER TABLE animal_costs        ADD COLUMN IF NOT EXISTS animal_uuid TEXT;
ALTER TABLE animal_movements    ADD COLUMN IF NOT EXISTS animal_uuid TEXT;
ALTER TABLE animal_photos       ADD COLUMN IF NOT EXISTS animal_uuid TEXT;
ALTER TABLE deaths              ADD COLUMN IF NOT EXISTS animal_uuid TEXT;
ALTER TABLE sales               ADD COLUMN IF NOT EXISTS animal_uuid TEXT;
ALTER TABLE insumo_transactions ADD COLUMN IF NOT EXISTS animal_uuid TEXT;

-- Idempotente: só preenche o que está nulo.
UPDATE weighings           t SET animal_uuid = a.uuid FROM animals a WHERE a.id = t.animal_id AND t.animal_uuid IS NULL;
UPDATE medications         t SET animal_uuid = a.uuid FROM animals a WHERE a.id = t.animal_id AND t.animal_uuid IS NULL;
UPDATE animal_costs        t SET animal_uuid = a.uuid FROM animals a WHERE a.id = t.animal_id AND t.animal_uuid IS NULL;
UPDATE animal_movements    t SET animal_uuid = a.uuid FROM animals a WHERE a.id = t.animal_id AND t.animal_uuid IS NULL;
UPDATE animal_photos       t SET animal_uuid = a.uuid FROM animals a WHERE a.id = t.animal_id AND t.animal_uuid IS NULL;
UPDATE deaths              t SET animal_uuid = a.uuid FROM animals a WHERE a.id = t.animal_id AND t.animal_uuid IS NULL;
UPDATE sales               t SET animal_uuid = a.uuid FROM animals a WHERE a.id = t.animal_id AND t.animal_uuid IS NULL;
UPDATE insumo_transactions t SET animal_uuid = a.uuid FROM animals a WHERE a.id = t.animal_id AND t.animal_uuid IS NULL;
