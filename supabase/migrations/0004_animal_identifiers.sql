-- ADR 0004 · etapa B1.3 — o brinco vira UM identificador, não a identidade
--
-- CONTEXTO
--   Terceira das seis etapas, ainda **aditiva**: nada em `animals` é alterado, e
--   as duas representações convivem. O número do brinco continua em `animals.id`
--   e passa a existir também como identificador de tipo `manejo`, vigente.
--
--   É esta etapa que torna possível o §4.2.3 — trocar brinco sem apagar o
--   anterior. Antes do ADR 0004 isso exigiria trocar a chave primária.
--
-- O ÍNDICE PARCIAL É O CORAÇÃO DA TABELA
--   `UNIQUE (tipo, valor) WHERE status = 'ativo'` atende ao §4.2.1/§4.2.2 (um
--   código ativo não pode estar em dois animais) **sem** impedir que o mesmo
--   valor apareça no histórico. É o que permite reaproveitar um brinco depois da
--   baixa, mantendo rastreável quem o usou antes.
--
-- VERIFICADO ANTES (2026-07-31)
--   backup conferido: backups/agrotop_20260731_232255.zip
--
-- VERIFICADO DEPOIS
--   14 animais · 14 identificadores 'manejo' ativos
--   sem identificador: 0 · valor divergente de animals.id: 0
--   weighings 42 e medications 24 intactos
--
-- ROLLBACK
--   DROP TABLE animal_identifiers;
--   (seguro: nada referencia esta tabela ainda)

CREATE TABLE IF NOT EXISTS animal_identifiers (
    id             bigserial PRIMARY KEY,
    animal_uuid    text NOT NULL,
    tipo           text NOT NULL,   -- manejo|oficial_pnib|visual|rfid|sisbov|privado
    valor          text NOT NULL,
    status         text NOT NULL DEFAULT 'ativo',   -- ativo|removido|inutilizado
    aplicado_em    text,
    removido_em    text,
    motivo_remocao text,
    aplicado_por   text,
    created_at     timestamptz DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_ident_ativo_unico
    ON animal_identifiers (tipo, valor) WHERE status = 'ativo';
CREATE INDEX IF NOT EXISTS idx_ident_animal
    ON animal_identifiers (animal_uuid);

-- Migra o brinco atual como identificador de manejo. Idempotente.
INSERT INTO animal_identifiers (animal_uuid, tipo, valor, status, aplicado_por)
SELECT a.uuid, 'manejo', a.id, 'ativo', 'migração ADR 0004'
  FROM animals a
 WHERE a.uuid IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM animal_identifiers i
                    WHERE i.animal_uuid = a.uuid AND i.tipo='manejo' AND i.status='ativo');
