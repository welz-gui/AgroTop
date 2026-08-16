-- Centro de custo (piquete) do custo fixo (Trilha 3 — ROADMAP §5)
--
-- CONTEXTO
--   `fixed_costs` sempre foi um balde único da fazenda inteira — não havia
--   como saber "quanto custou manter o Piquete Norte" separado de "quanto
--   custou o Curral". `services/centros_de_custo.py::consolidar` junta esse
--   custo fixo alocado com o custo por animal (já existente, agregado pelo
--   piquete atual de cada animal) num retrato por centro de custo.
--
-- UMA COLUNA NOVA, ADITIVA
--   fixed_costs.lote_id — o piquete a que este custo fixo pertence.
--   `NULL` é um valor VÁLIDO, não "esqueceram de preencher": significa
--   "Geral da Fazenda" — custo que não é de nenhum piquete específico
--   (salário do gerente, contabilidade, impostos).
--
-- ADITIVA
--   Uma coluna nova, anulável, em tabela existente. Nenhuma linha é lida,
--   alterada ou apagada. Todo custo fixo já lançado antes desta migration
--   fica, corretamente, "Geral da Fazenda" — não tinha como estar alocado
--   a um piquete, a coluna não existia.
--
-- ROLLBACK
--   ALTER TABLE fixed_costs DROP COLUMN IF EXISTS lote_id;
--   -- Depois: reverter o commit e regenerar baseline e retrato.

BEGIN;

ALTER TABLE fixed_costs ADD COLUMN IF NOT EXISTS lote_id TEXT REFERENCES lotes(id);
COMMENT ON COLUMN fixed_costs.lote_id IS
    'Centro de custo (piquete). NULL = Geral da Fazenda, não alocado a um piquete específico.';

CREATE INDEX IF NOT EXISTS idx_fixed_costs_lote ON fixed_costs (lote_id);

COMMIT;
