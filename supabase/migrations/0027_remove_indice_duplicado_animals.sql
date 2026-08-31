-- Remove índice único duplicado na tabela animals (aplicada em produção em
-- 2026-08-28 via MCP; este arquivo fecha a lacuna retroativamente, para o
-- histórico local ficar completo — mesmo padrão da migration 0016).
--
-- CONTEXTO
--   O advisor de performance do Supabase (lint 0009_duplicate_index) apontou
--   dois índices únicos idênticos sobre animals(uuid):
--     - animals_pkey        — chave primária (migration 0017/animals_uuid_vira_pk)
--     - animals_uuid_key    — UNIQUE remanescente de antes da 0017
--                             (migration animals_uuid_surrogate, 2026-07-31)
--   A 0017 tornou a constraint antiga redundante: dois índices únicos sobre a
--   mesma coluna, custo de manutenção em dobro em toda escrita, zero ganho de
--   integridade.
--
-- OBSTÁCULO
--   `DROP CONSTRAINT animals_uuid_key` sozinho falha (2BP01): 14 foreign keys
--   em produção foram criadas apontando especificamente para esse índice, não
--   para animals_pkey. `DROP ... CASCADE` removeria as 14 FKs junto — perda de
--   integridade referencial incompatível com "só remover um índice duplicado".
--
-- SOLUÇÃO
--   Numa única transação: drop das 14 FKs → drop de animals_uuid_key (agora
--   sem dependentes) → recreate das 14 FKs, definição idêntica à original,
--   agora apoiadas em animals_pkey (único índice único restante sobre uuid).
--   Cada definição de FK foi conferida antes (pg_get_constraintdef): todas
--   `FOREIGN KEY (coluna) REFERENCES animals(uuid)` simples, sem ON DELETE/
--   UPDATE especial, não deferráveis, já validadas.
--
-- VERIFICAÇÃO PÓS-APLICAÇÃO (conferida em produção)
--   - animals_uuid_key não aparece mais em pg_indexes.
--   - As 14 FKs recriadas aparecem com convalidated = true.
--   - O lint duplicate_index para public.animals não aparece mais no advisor.
--
-- ROLLBACK
--   BEGIN;
--   ALTER TABLE public.animal_costs DROP CONSTRAINT fk_animal_costs_animal_uuid;
--   ALTER TABLE public.animal_events DROP CONSTRAINT animal_events_animal_uuid_fkey;
--   ALTER TABLE public.animal_movements DROP CONSTRAINT fk_animal_movements_animal_uuid;
--   ALTER TABLE public.animal_photos DROP CONSTRAINT fk_animal_photos_animal_uuid;
--   ALTER TABLE public.animals DROP CONSTRAINT fk_animals_pai;
--   ALTER TABLE public.animals DROP CONSTRAINT fk_animals_mae;
--   ALTER TABLE public.deaths DROP CONSTRAINT fk_deaths_animal_uuid;
--   ALTER TABLE public.dispositivos DROP CONSTRAINT dispositivos_animal_uuid_fkey;
--   ALTER TABLE public.insumo_transactions DROP CONSTRAINT fk_insumo_trans_animal_uuid;
--   ALTER TABLE public.medications DROP CONSTRAINT fk_medications_animal_uuid;
--   ALTER TABLE public.movimentacao_animais DROP CONSTRAINT movimentacao_animais_animal_uuid_fkey;
--   ALTER TABLE public.partos DROP CONSTRAINT partos_mae_uuid_fkey;
--   ALTER TABLE public.sales DROP CONSTRAINT fk_sales_animal_uuid;
--   ALTER TABLE public.weighings DROP CONSTRAINT fk_weighings_animal_uuid;
--
--   ALTER TABLE public.animals ADD CONSTRAINT animals_uuid_key UNIQUE (uuid);
--
--   ALTER TABLE public.animal_costs ADD CONSTRAINT fk_animal_costs_animal_uuid FOREIGN KEY (animal_uuid) REFERENCES public.animals(uuid);
--   ALTER TABLE public.animal_events ADD CONSTRAINT animal_events_animal_uuid_fkey FOREIGN KEY (animal_uuid) REFERENCES public.animals(uuid);
--   ALTER TABLE public.animal_movements ADD CONSTRAINT fk_animal_movements_animal_uuid FOREIGN KEY (animal_uuid) REFERENCES public.animals(uuid);
--   ALTER TABLE public.animal_photos ADD CONSTRAINT fk_animal_photos_animal_uuid FOREIGN KEY (animal_uuid) REFERENCES public.animals(uuid);
--   ALTER TABLE public.animals ADD CONSTRAINT fk_animals_pai FOREIGN KEY (pai_uuid) REFERENCES public.animals(uuid);
--   ALTER TABLE public.animals ADD CONSTRAINT fk_animals_mae FOREIGN KEY (mae_uuid) REFERENCES public.animals(uuid);
--   ALTER TABLE public.deaths ADD CONSTRAINT fk_deaths_animal_uuid FOREIGN KEY (animal_uuid) REFERENCES public.animals(uuid);
--   ALTER TABLE public.dispositivos ADD CONSTRAINT dispositivos_animal_uuid_fkey FOREIGN KEY (animal_uuid) REFERENCES public.animals(uuid);
--   ALTER TABLE public.insumo_transactions ADD CONSTRAINT fk_insumo_trans_animal_uuid FOREIGN KEY (animal_uuid) REFERENCES public.animals(uuid);
--   ALTER TABLE public.medications ADD CONSTRAINT fk_medications_animal_uuid FOREIGN KEY (animal_uuid) REFERENCES public.animals(uuid);
--   ALTER TABLE public.movimentacao_animais ADD CONSTRAINT movimentacao_animais_animal_uuid_fkey FOREIGN KEY (animal_uuid) REFERENCES public.animals(uuid);
--   ALTER TABLE public.partos ADD CONSTRAINT partos_mae_uuid_fkey FOREIGN KEY (mae_uuid) REFERENCES public.animals(uuid);
--   ALTER TABLE public.sales ADD CONSTRAINT fk_sales_animal_uuid FOREIGN KEY (animal_uuid) REFERENCES public.animals(uuid);
--   ALTER TABLE public.weighings ADD CONSTRAINT fk_weighings_animal_uuid FOREIGN KEY (animal_uuid) REFERENCES public.animals(uuid);
--   COMMIT;

BEGIN;

ALTER TABLE public.animal_costs DROP CONSTRAINT fk_animal_costs_animal_uuid;
ALTER TABLE public.animal_events DROP CONSTRAINT animal_events_animal_uuid_fkey;
ALTER TABLE public.animal_movements DROP CONSTRAINT fk_animal_movements_animal_uuid;
ALTER TABLE public.animal_photos DROP CONSTRAINT fk_animal_photos_animal_uuid;
ALTER TABLE public.animals DROP CONSTRAINT fk_animals_pai;
ALTER TABLE public.animals DROP CONSTRAINT fk_animals_mae;
ALTER TABLE public.deaths DROP CONSTRAINT fk_deaths_animal_uuid;
ALTER TABLE public.dispositivos DROP CONSTRAINT dispositivos_animal_uuid_fkey;
ALTER TABLE public.insumo_transactions DROP CONSTRAINT fk_insumo_trans_animal_uuid;
ALTER TABLE public.medications DROP CONSTRAINT fk_medications_animal_uuid;
ALTER TABLE public.movimentacao_animais DROP CONSTRAINT movimentacao_animais_animal_uuid_fkey;
ALTER TABLE public.partos DROP CONSTRAINT partos_mae_uuid_fkey;
ALTER TABLE public.sales DROP CONSTRAINT fk_sales_animal_uuid;
ALTER TABLE public.weighings DROP CONSTRAINT fk_weighings_animal_uuid;

-- IF EXISTS: em replay a partir de 0000_baseline_producao.sql (dump de schema,
-- não histórico incremental), o Postgres pode já ter amarrado as 14 FKs a
-- animals_pkey na criação (não preserva qual índice cada FK usava
-- originalmente em produção) — nesse cenário animals_uuid_key nunca chega a
-- ficar referenciado, e pode já não existir isoladamente. Em produção real
-- (onde esta migration já foi aplicada via MCP, ver histórico acima) o
-- comportamento documentado nas seções anteriores é o que de fato ocorreu.
ALTER TABLE public.animals DROP CONSTRAINT IF EXISTS animals_uuid_key;

ALTER TABLE public.animal_costs ADD CONSTRAINT fk_animal_costs_animal_uuid FOREIGN KEY (animal_uuid) REFERENCES public.animals(uuid);
ALTER TABLE public.animal_events ADD CONSTRAINT animal_events_animal_uuid_fkey FOREIGN KEY (animal_uuid) REFERENCES public.animals(uuid);
ALTER TABLE public.animal_movements ADD CONSTRAINT fk_animal_movements_animal_uuid FOREIGN KEY (animal_uuid) REFERENCES public.animals(uuid);
ALTER TABLE public.animal_photos ADD CONSTRAINT fk_animal_photos_animal_uuid FOREIGN KEY (animal_uuid) REFERENCES public.animals(uuid);
ALTER TABLE public.animals ADD CONSTRAINT fk_animals_pai FOREIGN KEY (pai_uuid) REFERENCES public.animals(uuid);
ALTER TABLE public.animals ADD CONSTRAINT fk_animals_mae FOREIGN KEY (mae_uuid) REFERENCES public.animals(uuid);
ALTER TABLE public.deaths ADD CONSTRAINT fk_deaths_animal_uuid FOREIGN KEY (animal_uuid) REFERENCES public.animals(uuid);
ALTER TABLE public.dispositivos ADD CONSTRAINT dispositivos_animal_uuid_fkey FOREIGN KEY (animal_uuid) REFERENCES public.animals(uuid);
ALTER TABLE public.insumo_transactions ADD CONSTRAINT fk_insumo_trans_animal_uuid FOREIGN KEY (animal_uuid) REFERENCES public.animals(uuid);
ALTER TABLE public.medications ADD CONSTRAINT fk_medications_animal_uuid FOREIGN KEY (animal_uuid) REFERENCES public.animals(uuid);
ALTER TABLE public.movimentacao_animais ADD CONSTRAINT movimentacao_animais_animal_uuid_fkey FOREIGN KEY (animal_uuid) REFERENCES public.animals(uuid);
ALTER TABLE public.partos ADD CONSTRAINT partos_mae_uuid_fkey FOREIGN KEY (mae_uuid) REFERENCES public.animals(uuid);
ALTER TABLE public.sales ADD CONSTRAINT fk_sales_animal_uuid FOREIGN KEY (animal_uuid) REFERENCES public.animals(uuid);
ALTER TABLE public.weighings ADD CONSTRAINT fk_weighings_animal_uuid FOREIGN KEY (animal_uuid) REFERENCES public.animals(uuid);

COMMIT;
