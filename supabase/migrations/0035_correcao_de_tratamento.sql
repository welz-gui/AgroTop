-- Correção de tratamento por revisão (plano de rastreabilidade, Fase 2)
--
-- CONTEXTO
--   Uma aplicação registrada errada (dose, produto, data, carência, animal) só
--   podia ser corrigida editando a linha na tela de administração ou não podia ser
--   corrigida. Em base de rastreabilidade o registro original não some: corrige-se
--   criando outro que aponta para ele, com o motivo (PNIB §6.3).
--
-- ESTRUTURA (todas em `medications`, todas anuláveis; sem backfill)
--   evento_id            — id do evento `manejo_sanitario` gravado junto da aplicação.
--                          Nulo nas aplicações anteriores a esta migration.
--   cancelada_em         — instante ISO 8601 do cancelamento. Nulo = aplicação vigente.
--   cancelada_por        — login de quem cancelou.
--   motivo_cancelamento  — obrigatório na camada de serviço quando cancelada_em é preenchido.
--   corrige_id           — na linha NOVA de uma correção, id da aplicação que ela substitui.
--
--   A linha cancelada permanece. Carência, alertas, inventário, custo de venda e
--   PDF de evidências só enxergam as vigentes (`cancelada_em IS NULL`); o histórico
--   da ficha mostra as duas.
--
-- ROLLBACK
--   ALTER TABLE public.medications
--       DROP COLUMN IF EXISTS evento_id,
--       DROP COLUMN IF EXISTS cancelada_em,
--       DROP COLUMN IF EXISTS cancelada_por,
--       DROP COLUMN IF EXISTS motivo_cancelamento,
--       DROP COLUMN IF EXISTS corrige_id;

BEGIN;

ALTER TABLE public.medications ADD COLUMN IF NOT EXISTS evento_id bigint;
ALTER TABLE public.medications ADD COLUMN IF NOT EXISTS cancelada_em text;
ALTER TABLE public.medications ADD COLUMN IF NOT EXISTS cancelada_por text;
ALTER TABLE public.medications ADD COLUMN IF NOT EXISTS motivo_cancelamento text;
ALTER TABLE public.medications ADD COLUMN IF NOT EXISTS corrige_id integer;

COMMIT;
