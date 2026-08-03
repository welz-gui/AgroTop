-- ADR 0004 · etapa B3 — nascimentos e vínculo materno (§7 e §4.3)
--
-- CONTEXTO
--   O §7 exige cadastro de nascimento com vínculo materno; o §4.3 pede mãe, pai
--   "quando conhecido", propriedade de nascimento e origem entre os dados
--   básicos do animal. Nada disso existia — o sistema só sabia comprar animal.
--
--   Depende da **B4** (propriedades), aplicada antes: nascimento acontece numa
--   propriedade, e a de nascimento é diferente da atual.
--
-- POR QUE `partos` É TABELA, E NÃO CAMPO DO ANIMAL
--   O §7.2 exige que gêmeos gerem "animais distintos ligados ao MESMO parto".
--   Com o parto como campo do animal, dois gêmeos teriam dois partos e a
--   informação de que nasceram juntos se perderia.
--
-- ETAPA ADITIVA
--   Uma tabela e seis colunas anuláveis. Nada existente é restringido; o
--   rollback é `DROP`.
--
--   `origem` nasce com default `'comprado'` porque é o que todo animal do
--   rebanho atual é: o sistema não registrava nascimento até agora. Marcar
--   todos como `'nascido'` seria afirmar um fato que não ocorreu.
--
-- ROLLBACK
--   ALTER TABLE animals DROP COLUMN propriedade_nascimento_id, mae_uuid,
--                              pai_uuid, parto_id, peso_nascimento, origem;
--   DROP TABLE partos;

BEGIN;

CREATE TABLE IF NOT EXISTS partos (
    id             text PRIMARY KEY,
    mae_uuid       text NOT NULL REFERENCES animals(uuid),
    data           text NOT NULL,
    hora           text,
    tipo_parto     text,
    condicao       text,
    propriedade_id text REFERENCES properties(id),
    responsavel    text,
    data_estimada  integer NOT NULL DEFAULT 0,
    observacoes    text,
    created_at     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_partos_mae
    ON partos USING btree (mae_uuid, data DESC);

ALTER TABLE animals ADD COLUMN IF NOT EXISTS propriedade_nascimento_id text;
ALTER TABLE animals ADD COLUMN IF NOT EXISTS mae_uuid        text;
ALTER TABLE animals ADD COLUMN IF NOT EXISTS pai_uuid        text;
ALTER TABLE animals ADD COLUMN IF NOT EXISTS parto_id        text;
ALTER TABLE animals ADD COLUMN IF NOT EXISTS peso_nascimento double precision;
ALTER TABLE animals ADD COLUMN IF NOT EXISTS origem          text NOT NULL DEFAULT 'comprado';

ALTER TABLE animals DROP CONSTRAINT IF EXISTS fk_animals_prop_nascimento;
ALTER TABLE animals ADD CONSTRAINT fk_animals_prop_nascimento
    FOREIGN KEY (propriedade_nascimento_id) REFERENCES properties(id);

ALTER TABLE animals DROP CONSTRAINT IF EXISTS fk_animals_mae;
ALTER TABLE animals ADD CONSTRAINT fk_animals_mae
    FOREIGN KEY (mae_uuid) REFERENCES animals(uuid);

ALTER TABLE animals DROP CONSTRAINT IF EXISTS fk_animals_pai;
ALTER TABLE animals ADD CONSTRAINT fk_animals_pai
    FOREIGN KEY (pai_uuid) REFERENCES animals(uuid);

ALTER TABLE animals DROP CONSTRAINT IF EXISTS fk_animals_parto;
ALTER TABLE animals ADD CONSTRAINT fk_animals_parto
    FOREIGN KEY (parto_id) REFERENCES partos(id);

CREATE INDEX IF NOT EXISTS idx_animals_mae  ON animals USING btree (mae_uuid);
CREATE INDEX IF NOT EXISTS idx_animals_parto ON animals USING btree (parto_id);

COMMIT;
