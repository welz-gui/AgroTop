-- Baseline do schema de produção do AgroTop
-- Gerado em 2026-07-31 por tools/dump_schema_nuvem.py
--
-- GERADO AUTOMATICAMENTE a partir do catálogo do Postgres.
-- NÃO cobre: triggers, funções, políticas de RLS, grants, extensões.
-- Para um dump completo, prefira `supabase db dump` ou `pg_dump`.
--
-- SEM QUALIFICAÇÃO DE SCHEMA de propósito: os nomes são resolvidos
-- pelo search_path, para que o mesmo arquivo sirva a qualquer tenant
-- (ver docs/adr/0001-multi-fazenda-schema-por-tenant.md). Aplicar com:
--     CREATE SCHEMA fazenda_2;  SET search_path TO fazenda_2;
--     \i supabase/migrations/0000_baseline_producao.sql
-- Validar com: python tools/testar_baseline.py

CREATE TABLE IF NOT EXISTS animal_costs (
    id bigserial,
    animal_id text NOT NULL,
    cost_type text DEFAULT 'operacional'::text NOT NULL,
    description text,
    amount double precision NOT NULL,
    cost_date text NOT NULL,
    notes text,
    created_at timestamp with time zone DEFAULT now(),
    animal_uuid text,
    CONSTRAINT animal_costs_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS animal_movements (
    id bigserial,
    animal_id text NOT NULL,
    from_lote_id text,
    to_lote_id text NOT NULL,
    movement_date text NOT NULL,
    reason text DEFAULT 'manejo'::text,
    operator text,
    notes text,
    created_at timestamp with time zone DEFAULT now(),
    animal_uuid text,
    CONSTRAINT animal_movements_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS animal_photos (
    id bigserial,
    animal_id text NOT NULL,
    image bytea NOT NULL,
    mime text DEFAULT 'image/jpeg'::text,
    taken_date text NOT NULL,
    operator text,
    created_at timestamp with time zone DEFAULT now(),
    animal_uuid text,
    CONSTRAINT animal_photos_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS animals (
    id text NOT NULL,
    breed text NOT NULL,
    sex text DEFAULT 'M'::text NOT NULL,
    birth_date text,
    birth_estimated integer DEFAULT 0,
    age_source text DEFAULT 'propriedade'::text,
    nf_number text,
    gta_number text,
    entry_date text NOT NULL,
    entry_weight double precision NOT NULL,
    current_weight double precision NOT NULL,
    target_weight double precision DEFAULT 500,
    status text DEFAULT 'ativo'::text NOT NULL,
    lote_id text,
    fornecedor_id bigint,
    purchase_price double precision DEFAULT 0,
    carcass_yield double precision DEFAULT 0.52,
    notes text,
    created_at timestamp with time zone DEFAULT now(),
    purchase_mode text DEFAULT 'cabeca'::text,
    purchase_lot_ref text,
    uuid text,
    CONSTRAINT animals_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS category_prices (
    id bigserial,
    age_band text NOT NULL,
    sex text NOT NULL,
    price_per_kg double precision DEFAULT 0,
    price_per_head double precision DEFAULT 0,
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT category_prices_pkey PRIMARY KEY (id),
    CONSTRAINT category_prices_age_band_sex_key UNIQUE (age_band, sex)
);

CREATE TABLE IF NOT EXISTS deaths (
    id bigserial,
    animal_id text NOT NULL,
    death_date text NOT NULL,
    cause text DEFAULT 'Desconhecida'::text NOT NULL,
    lote_id text,
    weight_at_death double precision,
    cost_at_death double precision DEFAULT 0,
    operator text,
    notes text,
    created_at timestamp with time zone DEFAULT now(),
    animal_uuid text,
    CONSTRAINT deaths_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS feeding_checks (
    id bigserial,
    plan_id bigint,
    lote_id text NOT NULL,
    check_date text NOT NULL,
    status text DEFAULT 'feito'::text NOT NULL,
    actual_quantity double precision,
    operator text,
    notes text,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT feeding_checks_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS feeding_plans (
    id bigserial,
    lote_id text NOT NULL,
    product_name text NOT NULL,
    insumo_id bigint,
    quantity double precision DEFAULT 0 NOT NULL,
    unit text DEFAULT 'kg'::text NOT NULL,
    frequency text DEFAULT 'diario'::text NOT NULL,
    active integer DEFAULT 1,
    notes text,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT feeding_plans_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS fixed_costs (
    id bigserial,
    category text DEFAULT 'outro'::text NOT NULL,
    description text,
    amount double precision NOT NULL,
    cost_date text NOT NULL,
    recurring integer DEFAULT 0,
    notes text,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT fixed_costs_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS fornecedores (
    id bigserial,
    name text NOT NULL,
    city text,
    state text DEFAULT 'MT'::text,
    contact text,
    notes text,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT fornecedores_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS health_protocols (
    id bigserial,
    name text NOT NULL,
    sex_target text DEFAULT 'ambos'::text NOT NULL,
    age_min integer DEFAULT 0,
    age_max integer DEFAULT 999,
    dose_value double precision DEFAULT 1,
    dose_ref_kg double precision DEFAULT 0,
    dose_unit text DEFAULT 'ml'::text,
    insumo_id bigint,
    frequency text DEFAULT 'anual'::text NOT NULL,
    withdrawal_days integer DEFAULT 0,
    route text DEFAULT 'Subcutânea'::text,
    active integer DEFAULT 1,
    notes text,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT health_protocols_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS insumo_transactions (
    id bigserial,
    insumo_id bigint NOT NULL,
    type text NOT NULL,
    quantity double precision NOT NULL,
    reason text,
    animal_id text,
    transaction_date text NOT NULL,
    operator text,
    notes text,
    created_at timestamp with time zone DEFAULT now(),
    lote_id text,
    animal_uuid text,
    CONSTRAINT insumo_transactions_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS insumos (
    id bigserial,
    name text NOT NULL,
    category text DEFAULT 'medicamento'::text NOT NULL,
    unit text DEFAULT 'ml'::text NOT NULL,
    current_stock double precision DEFAULT 0 NOT NULL,
    min_stock double precision DEFAULT 0 NOT NULL,
    cost_per_unit double precision DEFAULT 0,
    supplier text,
    notes text,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT insumos_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS lotes (
    id text NOT NULL,
    name text NOT NULL,
    area_ha double precision DEFAULT 0,
    capacity_ua double precision DEFAULT 0,
    status text DEFAULT 'ativo'::text,
    last_entry_date text,
    last_exit_date text,
    notes text,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT lotes_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS medications (
    id bigserial,
    animal_id text NOT NULL,
    medication_name text NOT NULL,
    dose double precision DEFAULT 0,
    unit text DEFAULT 'ml'::text,
    application_route text DEFAULT 'Subcutânea'::text,
    withdrawal_days integer DEFAULT 0,
    med_date text NOT NULL,
    applied_by text,
    insumo_id bigint,
    notes text,
    created_at timestamp with time zone DEFAULT now(),
    protocol_id bigint,
    animal_uuid text,
    CONSTRAINT medications_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS pluviometria (
    id bigserial,
    read_date text NOT NULL,
    rain_mm double precision DEFAULT 0 NOT NULL,
    lote_id text,
    operator text,
    notes text,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT pluviometria_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS sales (
    id bigserial,
    animal_id text NOT NULL,
    sale_date text NOT NULL,
    sale_type text DEFAULT 'abate'::text NOT NULL,
    pricing_mode text DEFAULT 'kg'::text NOT NULL,
    weight_kg double precision,
    price_per_kg double precision,
    total_value double precision DEFAULT 0 NOT NULL,
    buyer text,
    lot_ref text,
    cost_at_sale double precision DEFAULT 0,
    profit double precision DEFAULT 0,
    operator text,
    notes text,
    created_at timestamp with time zone DEFAULT now(),
    animal_uuid text,
    CONSTRAINT sales_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS sessions (
    token text NOT NULL,
    user_id bigint,
    expires_at text,
    CONSTRAINT sessions_pkey PRIMARY KEY (token)
);

CREATE TABLE IF NOT EXISTS settings (
    key text NOT NULL,
    value text,
    CONSTRAINT settings_pkey PRIMARY KEY (key)
);

CREATE TABLE IF NOT EXISTS users (
    id bigserial,
    username text NOT NULL,
    password_hash text NOT NULL,
    name text NOT NULL,
    role text DEFAULT 'operator'::text NOT NULL,
    CONSTRAINT users_pkey PRIMARY KEY (id),
    CONSTRAINT users_username_key UNIQUE (username)
);

CREATE TABLE IF NOT EXISTS weighings (
    id bigserial,
    animal_id text NOT NULL,
    weight double precision NOT NULL,
    weigh_date text NOT NULL,
    lote_id text,
    operator text,
    method text DEFAULT 'pesado'::text,
    notes text,
    created_at timestamp with time zone DEFAULT now(),
    animal_uuid text,
    CONSTRAINT weighings_pkey PRIMARY KEY (id)
);

-- Chaves estrangeiras aplicadas ao final: assim a ordem de
-- criação das tabelas acima não importa.
ALTER TABLE animal_costs ADD CONSTRAINT animal_costs_animal_id_fkey FOREIGN KEY (animal_id) REFERENCES animals(id);
ALTER TABLE animal_movements ADD CONSTRAINT animal_movements_animal_id_fkey FOREIGN KEY (animal_id) REFERENCES animals(id);
ALTER TABLE animal_photos ADD CONSTRAINT animal_photos_animal_id_fkey FOREIGN KEY (animal_id) REFERENCES animals(id);
ALTER TABLE animals ADD CONSTRAINT animals_fornecedor_id_fkey FOREIGN KEY (fornecedor_id) REFERENCES fornecedores(id);
ALTER TABLE animals ADD CONSTRAINT animals_lote_id_fkey FOREIGN KEY (lote_id) REFERENCES lotes(id);
ALTER TABLE deaths ADD CONSTRAINT deaths_animal_id_fkey FOREIGN KEY (animal_id) REFERENCES animals(id);
ALTER TABLE feeding_checks ADD CONSTRAINT feeding_checks_plan_id_fkey FOREIGN KEY (plan_id) REFERENCES feeding_plans(id);
ALTER TABLE feeding_plans ADD CONSTRAINT feeding_plans_insumo_id_fkey FOREIGN KEY (insumo_id) REFERENCES insumos(id);
ALTER TABLE feeding_plans ADD CONSTRAINT feeding_plans_lote_id_fkey FOREIGN KEY (lote_id) REFERENCES lotes(id);
ALTER TABLE health_protocols ADD CONSTRAINT health_protocols_insumo_id_fkey FOREIGN KEY (insumo_id) REFERENCES insumos(id);
ALTER TABLE insumo_transactions ADD CONSTRAINT insumo_transactions_insumo_id_fkey FOREIGN KEY (insumo_id) REFERENCES insumos(id);
ALTER TABLE medications ADD CONSTRAINT medications_animal_id_fkey FOREIGN KEY (animal_id) REFERENCES animals(id);
ALTER TABLE medications ADD CONSTRAINT medications_insumo_id_fkey FOREIGN KEY (insumo_id) REFERENCES insumos(id);
ALTER TABLE sales ADD CONSTRAINT sales_animal_id_fkey FOREIGN KEY (animal_id) REFERENCES animals(id);
ALTER TABLE weighings ADD CONSTRAINT weighings_animal_id_fkey FOREIGN KEY (animal_id) REFERENCES animals(id);

-- Índices (fora das constraints)
CREATE INDEX IF NOT EXISTS idx_animal_costs_animal ON animal_costs USING btree (animal_id);
CREATE INDEX IF NOT EXISTS idx_animal_photos_animal ON animal_photos USING btree (animal_id);
CREATE INDEX IF NOT EXISTS idx_animals_lote ON animals USING btree (lote_id);
CREATE INDEX IF NOT EXISTS idx_animals_status ON animals USING btree (status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_animals_uuid ON animals USING btree (uuid);
CREATE INDEX IF NOT EXISTS idx_deaths_date ON deaths USING btree (death_date);
CREATE INDEX IF NOT EXISTS idx_insumo_trans_lote ON insumo_transactions USING btree (lote_id);
CREATE INDEX IF NOT EXISTS idx_insumo_trans_reason ON insumo_transactions USING btree (reason);
CREATE INDEX IF NOT EXISTS idx_medications_animal ON medications USING btree (animal_id);
CREATE INDEX IF NOT EXISTS idx_medications_protocol ON medications USING btree (protocol_id);
CREATE INDEX IF NOT EXISTS idx_pluvio_date ON pluviometria USING btree (read_date);
CREATE INDEX IF NOT EXISTS idx_pluvio_lote ON pluviometria USING btree (lote_id);
CREATE INDEX IF NOT EXISTS idx_sales_date ON sales USING btree (sale_date);
CREATE INDEX IF NOT EXISTS idx_weighings_animal_date ON weighings USING btree (animal_id, weigh_date DESC);
CREATE INDEX IF NOT EXISTS idx_weighings_date ON weighings USING btree (weigh_date DESC);

