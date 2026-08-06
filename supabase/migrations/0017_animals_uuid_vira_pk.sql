-- B1.7 (ADR 0004 §4.1): uuid vira a PK de animals; id (brinco) vira UNIQUE comum.
--
-- As etapas B1.1-B1.6 já tinham deixado uuid NOT NULL/UNIQUE (etapa 1) e
-- migrado as treze tabelas com FK para animals a apontarem para
-- animals(uuid), nunca para animals(id) (etapa 5) — conferido: zero FKs
-- restantes para animals(id) em todo o histórico de migrations. O vínculo
-- real já era o uuid; faltava só a PK do SQL reconhecer isso.
--
-- Sem impacto em código de aplicação: nenhuma query depende de "qual coluna
-- é a PK", todas referenciam id/uuid pelo nome explícito.
ALTER TABLE animals DROP CONSTRAINT animals_pkey;
ALTER TABLE animals ADD CONSTRAINT animals_pkey PRIMARY KEY (uuid);
ALTER TABLE animals ADD CONSTRAINT animals_id_key UNIQUE (id);
