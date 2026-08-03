-- ADR 0004 · etapa B4 — hierarquia Organização → Produtor → Propriedade (§3)
--
-- CONTEXTO
--   O PNIB exige a hierarquia **mesmo com uma fazenda só** (§3), porque o titular
--   pode ter várias propriedades e movimentar animais entre elas (§8.1). Até
--   aqui, `lote_id` (piquete) era a única noção de lugar no sistema — e piquete
--   não é estabelecimento perante o órgão.
--
--   Destrava a **B3** (nascimento acontece numa propriedade) e a **B6**
--   (movimentação entre propriedades). Fazer B3 antes obrigaria a refazê-la.
--
-- ETAPA ADITIVA
--   Três tabelas novas e duas colunas **anuláveis**. Nada existente é restringido.
--   Rollback é `DROP`. A obrigatoriedade de `property_id` vem na **B4.3**, depois
--   de as escritas preencherem — mesma ordem que funcionou no B1, e pelo mesmo
--   motivo: restrição antes da escrita deixa toda linha nova com o campo nulo.
--
-- IDENTIFICADOR IMUTÁVEL (§3.4)
--   `properties.id` é interno e não muda. O `codigo_oficial` do estabelecimento
--   pode mudar, ou nem existir ainda — mesma razão de o animal ter uuid separado
--   do brinco.
--
-- ROLLBACK
--   ALTER TABLE animals DROP COLUMN property_id;
--   ALTER TABLE lotes   DROP COLUMN property_id;
--   DROP TABLE properties;
--   DROP TABLE produtores;
--   DROP TABLE organizacoes;

BEGIN;

CREATE TABLE IF NOT EXISTS organizacoes (
    id                text PRIMARY KEY,
    nome              text NOT NULL,
    documento         text,
    responsavel_legal text,
    contato           text,
    status            text NOT NULL DEFAULT 'ativa',
    created_at        timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS produtores (
    id                 text PRIMARY KEY,
    organizacao_id     text NOT NULL REFERENCES organizacoes(id),
    nome               text NOT NULL,
    documento          text,
    inscricao_estadual text,
    contato            text,
    status             text NOT NULL DEFAULT 'ativo',
    created_at         timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS properties (
    id             text PRIMARY KEY,
    produtor_id    text NOT NULL REFERENCES produtores(id),
    nome           text NOT NULL,
    codigo_oficial text,
    municipio      text,
    uf             text,
    endereco       text,
    latitude       double precision,
    longitude      double precision,
    poligono       text,
    atividade      text,
    situacao       text NOT NULL DEFAULT 'ativa',
    inicio         text,
    encerramento   text,
    created_at     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_properties_produtor
    ON properties USING btree (produtor_id);

-- Índice parcial: código oficial é único quando existe, mas a maioria das
-- propriedades ainda não tem um. `UNIQUE` simples recusaria o segundo NULL em
-- alguns bancos e impediria cadastrar duas propriedades sem código.
CREATE UNIQUE INDEX IF NOT EXISTS idx_properties_codigo_oficial
    ON properties USING btree (codigo_oficial)
    WHERE codigo_oficial IS NOT NULL;

ALTER TABLE animals ADD COLUMN IF NOT EXISTS property_id text;
ALTER TABLE lotes   ADD COLUMN IF NOT EXISTS property_id text;

ALTER TABLE animals DROP CONSTRAINT IF EXISTS fk_animals_property;
ALTER TABLE animals ADD CONSTRAINT fk_animals_property
    FOREIGN KEY (property_id) REFERENCES properties(id);

ALTER TABLE lotes DROP CONSTRAINT IF EXISTS fk_lotes_property;
ALTER TABLE lotes ADD CONSTRAINT fk_lotes_property
    FOREIGN KEY (property_id) REFERENCES properties(id);

CREATE INDEX IF NOT EXISTS idx_animals_property
    ON animals USING btree (property_id);

COMMIT;
