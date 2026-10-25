-- Revisão de pesagem e movimentação (plano de rastreabilidade, Fase 2)
--
-- CONTEXTO
--   A migration 0035 deu ao tratamento o fluxo de correção por revisão: o registro
--   errado não some nem é editado, é cancelado ou substituído por outro que aponta para
--   ele, com motivo e autor (PNIB §6.3). Esta estende o mesmo desenho a `weighings` e
--   `animal_movements`, os outros dois eventos canônicos.
--
-- ESTRUTURA (as mesmas cinco colunas, nas duas tabelas, todas anuláveis; sem backfill)
--   evento_id            — id do evento (`pesagem` / `mudanca_lote`) gravado junto do
--                          registro. Nulo nos registros anteriores a esta migration.
--   cancelada_em         — instante ISO 8601 do cancelamento. Nulo = registro vigente.
--   cancelada_por        — login de quem cancelou.
--   motivo_cancelamento  — obrigatório na camada de serviço quando cancelada_em é preenchido.
--   corrige_id           — na linha NOVA de uma correção, id do registro que ela substitui.
--
--   A linha cancelada permanece. Peso atual, GMD, histórico de movimentação e datas do
--   piquete só enxergam os vigentes (`cancelada_em IS NULL`).
--
-- ROLLBACK
--   ALTER TABLE public.weighings
--       DROP COLUMN IF EXISTS evento_id, DROP COLUMN IF EXISTS cancelada_em,
--       DROP COLUMN IF EXISTS cancelada_por, DROP COLUMN IF EXISTS motivo_cancelamento,
--       DROP COLUMN IF EXISTS corrige_id;
--   ALTER TABLE public.animal_movements
--       DROP COLUMN IF EXISTS evento_id, DROP COLUMN IF EXISTS cancelada_em,
--       DROP COLUMN IF EXISTS cancelada_por, DROP COLUMN IF EXISTS motivo_cancelamento,
--       DROP COLUMN IF EXISTS corrige_id;

BEGIN;

ALTER TABLE public.weighings ADD COLUMN IF NOT EXISTS evento_id bigint;
ALTER TABLE public.weighings ADD COLUMN IF NOT EXISTS cancelada_em text;
ALTER TABLE public.weighings ADD COLUMN IF NOT EXISTS cancelada_por text;
ALTER TABLE public.weighings ADD COLUMN IF NOT EXISTS motivo_cancelamento text;
ALTER TABLE public.weighings ADD COLUMN IF NOT EXISTS corrige_id integer;

ALTER TABLE public.animal_movements ADD COLUMN IF NOT EXISTS evento_id bigint;
ALTER TABLE public.animal_movements ADD COLUMN IF NOT EXISTS cancelada_em text;
ALTER TABLE public.animal_movements ADD COLUMN IF NOT EXISTS cancelada_por text;
ALTER TABLE public.animal_movements ADD COLUMN IF NOT EXISTS motivo_cancelamento text;
ALTER TABLE public.animal_movements ADD COLUMN IF NOT EXISTS corrige_id integer;

COMMIT;
