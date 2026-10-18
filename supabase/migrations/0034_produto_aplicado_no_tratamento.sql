-- Produto aplicado no tratamento: princípio ativo, lote e validade
-- (plano de rastreabilidade, Fase 2: "tratamento defensável")
--
-- CONTEXTO
--   `medications` guardava produto, dose, unidade, via, carência, data e
--   responsável, mas não dizia QUAL princípio ativo foi aplicado, de QUAL lote e
--   com que validade. Sem isso o tratamento não responde à pergunta que a
--   rastreabilidade faz.
--
-- ESTRUTURA
--   medications.principio_ativo   — o que foi aplicado (texto livre, opcional).
--   medications.lote_produto      — lote da embalagem usada (opcional).
--   medications.validade_produto  — validade da embalagem, AAAA-MM-DD (opcional).
--     A aplicação recusa validade anterior à data da aplicação (regra na camada de
--     serviço, `services/tratamento.py`; o banco só guarda).
--   insumos.principio_ativo       — padrão do cadastro: quando a aplicação não
--     informa o princípio ativo e liga um insumo, usa-se este.
--
--   Sem backfill: registros antigos ficam com NULL ("não informado"), que é a
--   verdade deles.
--
-- ROLLBACK
--   ALTER TABLE public.medications
--       DROP COLUMN IF EXISTS principio_ativo,
--       DROP COLUMN IF EXISTS lote_produto,
--       DROP COLUMN IF EXISTS validade_produto;
--   ALTER TABLE public.insumos DROP COLUMN IF EXISTS principio_ativo;

BEGIN;

ALTER TABLE public.medications ADD COLUMN IF NOT EXISTS principio_ativo text;
ALTER TABLE public.medications ADD COLUMN IF NOT EXISTS lote_produto text;
ALTER TABLE public.medications ADD COLUMN IF NOT EXISTS validade_produto text;

ALTER TABLE public.insumos ADD COLUMN IF NOT EXISTS principio_ativo text;

COMMIT;
