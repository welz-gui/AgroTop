-- ADR 0004 · etapa B1.5 — as FKs passam a apontar para `animals(uuid)`
--
-- CONTEXTO
--   **Primeira etapa que restringe** em vez de acrescentar. Só é segura porque a
--   etapa 4 fez toda escrita preencher o espelho — a restrição encontra dado
--   consistente, em vez de ter que consertá-lo.
--
--   As FKs antigas em `animal_id` são **mantidas**. Duas restrições ativas ao
--   mesmo tempo, ambas satisfeitas: é o que mantém a etapa reversível. A remoção
--   do `animal_id` é a etapa 6.
--
-- O DETALHE QUE QUASE PASSA DESPERCEBIDO
--   No Postgres, **índice único não serve como alvo de FK** — é preciso uma
--   UNIQUE CONSTRAINT. A etapa 1 criou apenas o índice `idx_animals_uuid`.
--   `ADD CONSTRAINT ... UNIQUE USING INDEX` promove o índice existente a
--   constraint, sem reconstruí-lo.
--
-- VERIFICADO ANTES (2026-08-01)
--   backup conferido: backups/agrotop_20260801_092345.zip
--   animals.uuid nulos: 0 · órfãos: 0
--   linhas sem espelho em weighings/medications/animal_costs/movements: 0
--
-- VERIFICADO DEPOIS
--   8 FKs criadas · animals.uuid NOT NULL · constraint animals_uuid_key
--   INSERT com uuid inexistente foi BLOQUEADO (foreign_key_violation)
--   42 linhas em weighings intactas · 0 linhas de teste deixadas
--
-- ROLLBACK
--   ALTER TABLE weighings           DROP CONSTRAINT fk_weighings_animal_uuid;
--   ALTER TABLE medications         DROP CONSTRAINT fk_medications_animal_uuid;
--   ALTER TABLE animal_costs        DROP CONSTRAINT fk_animal_costs_animal_uuid;
--   ALTER TABLE animal_movements    DROP CONSTRAINT fk_animal_movements_animal_uuid;
--   ALTER TABLE animal_photos       DROP CONSTRAINT fk_animal_photos_animal_uuid;
--   ALTER TABLE deaths              DROP CONSTRAINT fk_deaths_animal_uuid;
--   ALTER TABLE sales               DROP CONSTRAINT fk_sales_animal_uuid;
--   ALTER TABLE insumo_transactions DROP CONSTRAINT fk_insumo_trans_animal_uuid;
--   ALTER TABLE animals DROP CONSTRAINT animals_uuid_key;
--   ALTER TABLE animals ALTER COLUMN uuid DROP NOT NULL;

ALTER TABLE animals ALTER COLUMN uuid SET NOT NULL;
ALTER TABLE animals ADD CONSTRAINT animals_uuid_key UNIQUE USING INDEX idx_animals_uuid;

-- `animal_uuid` segue nullable: `insumo_transactions` tem linhas legítimas sem
-- animal (compra, trato_lote), e FK não restringe NULL.
ALTER TABLE weighings           ADD CONSTRAINT fk_weighings_animal_uuid        FOREIGN KEY (animal_uuid) REFERENCES animals(uuid);
ALTER TABLE medications         ADD CONSTRAINT fk_medications_animal_uuid      FOREIGN KEY (animal_uuid) REFERENCES animals(uuid);
ALTER TABLE animal_costs        ADD CONSTRAINT fk_animal_costs_animal_uuid     FOREIGN KEY (animal_uuid) REFERENCES animals(uuid);
ALTER TABLE animal_movements    ADD CONSTRAINT fk_animal_movements_animal_uuid FOREIGN KEY (animal_uuid) REFERENCES animals(uuid);
ALTER TABLE animal_photos       ADD CONSTRAINT fk_animal_photos_animal_uuid    FOREIGN KEY (animal_uuid) REFERENCES animals(uuid);
ALTER TABLE deaths              ADD CONSTRAINT fk_deaths_animal_uuid           FOREIGN KEY (animal_uuid) REFERENCES animals(uuid);
ALTER TABLE sales               ADD CONSTRAINT fk_sales_animal_uuid            FOREIGN KEY (animal_uuid) REFERENCES animals(uuid);
ALTER TABLE insumo_transactions ADD CONSTRAINT fk_insumo_trans_animal_uuid     FOREIGN KEY (animal_uuid) REFERENCES animals(uuid);
