-- Revisão de custo, óbito e venda por cancelamento ou correção (plano de rastreabilidade, Fase 2)
--
-- CONTEXTO
--   Tratamento (0035), pesagem e movimentação (0036) já se corrigem sem apagar. Faltavam os
--   custos (de animal e fixos), o óbito e a venda: um lançamento errado só saía editando a linha
--   na tela de administração ou apagando. Em base de rastreabilidade o registro original não
--   some: corrige-se criando outro que aponta para ele, com o motivo (PNIB §6.3).
--
-- ESTRUTURA (anuláveis; sem backfill) — as mesmas colunas da 0035/0036
--   cancelada_em         — instante ISO 8601 do cancelamento. Nulo = registro vigente.
--   cancelada_por        — login de quem cancelou.
--   motivo_cancelamento  — obrigatório na camada de serviço quando cancelada_em é preenchido.
--   corrige_id           — na linha NOVA de uma correção, id do registro que ela substitui.
--   evento_id            — só em `deaths` e `sales`, que têm evento do animal (`morte`, `venda`):
--                          id do evento gravado junto, para a cadeia de revisão (estorno).
--                          Nulo nos registros anteriores a esta migration.
--
--   A linha cancelada permanece. Somas, DRE, mortalidade, custo por animal e por piquete só
--   enxergam as vigentes (`cancelada_em IS NULL`).
--
-- ROLLBACK
--   ALTER TABLE public.animal_costs DROP COLUMN IF EXISTS cancelada_em, DROP COLUMN IF EXISTS cancelada_por,
--       DROP COLUMN IF EXISTS motivo_cancelamento, DROP COLUMN IF EXISTS corrige_id;
--   (idem fixed_costs; deaths e sales também com DROP COLUMN IF EXISTS evento_id)

BEGIN;

ALTER TABLE public.animal_costs ADD COLUMN IF NOT EXISTS cancelada_em text;
ALTER TABLE public.animal_costs ADD COLUMN IF NOT EXISTS cancelada_por text;
ALTER TABLE public.animal_costs ADD COLUMN IF NOT EXISTS motivo_cancelamento text;
ALTER TABLE public.animal_costs ADD COLUMN IF NOT EXISTS corrige_id integer;

ALTER TABLE public.fixed_costs ADD COLUMN IF NOT EXISTS cancelada_em text;
ALTER TABLE public.fixed_costs ADD COLUMN IF NOT EXISTS cancelada_por text;
ALTER TABLE public.fixed_costs ADD COLUMN IF NOT EXISTS motivo_cancelamento text;
ALTER TABLE public.fixed_costs ADD COLUMN IF NOT EXISTS corrige_id integer;

ALTER TABLE public.deaths ADD COLUMN IF NOT EXISTS evento_id bigint;
ALTER TABLE public.deaths ADD COLUMN IF NOT EXISTS cancelada_em text;
ALTER TABLE public.deaths ADD COLUMN IF NOT EXISTS cancelada_por text;
ALTER TABLE public.deaths ADD COLUMN IF NOT EXISTS motivo_cancelamento text;
ALTER TABLE public.deaths ADD COLUMN IF NOT EXISTS corrige_id integer;

ALTER TABLE public.sales ADD COLUMN IF NOT EXISTS evento_id bigint;
ALTER TABLE public.sales ADD COLUMN IF NOT EXISTS cancelada_em text;
ALTER TABLE public.sales ADD COLUMN IF NOT EXISTS cancelada_por text;
ALTER TABLE public.sales ADD COLUMN IF NOT EXISTS motivo_cancelamento text;
ALTER TABLE public.sales ADD COLUMN IF NOT EXISTS corrige_id integer;

COMMIT;
