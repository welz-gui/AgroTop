-- Piquete do animal na data da aplicação (plano de rastreabilidade, comparação com outros sistemas)
--
-- CONTEXTO
--   A pesagem guarda o piquete (`weighings.lote_id`), a aplicação não. Para o dossiê, "onde o
--   animal estava quando foi tratado" só dava para reconstruir cruzando a data com as
--   movimentações, a cada leitura. Passa a ficar gravado na própria aplicação.
--
-- ESTRUTURA (`medications`, anulável; sem backfill)
--   lote_id  — piquete do animal NA DATA DA APLICAÇÃO (`med_date`), e não no momento do
--              registro: aplicação feita offline ou retroativa leva o piquete da data
--              (a camada de dados olha a primeira movimentação vigente depois da data). Nulo
--              nas aplicações anteriores a esta migration e nas de animal sem piquete.
--              Sem chave estrangeira, como `weighings.lote_id`: o piquete pode ser removido
--              depois sem apagar a aplicação.
--
-- ROLLBACK
--   ALTER TABLE public.medications DROP COLUMN IF EXISTS lote_id;

BEGIN;

ALTER TABLE public.medications ADD COLUMN IF NOT EXISTS lote_id text;

COMMIT;
