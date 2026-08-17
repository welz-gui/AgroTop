-- Vigência do item de trato — dietas versionadas (Trilha 3 — ROADMAP §5)
--
-- CONTEXTO
--   `feeding_plans` só tinha um interruptor `active` — mudar a quantidade
--   ou a frequência de um item reescrevia o valor no lugar (não havia nem
--   função de UPDATE de quantidade; a única forma real de "mudar a dieta"
--   era pausar/reativar o mesmo valor, ou apagar e recriar, perdendo o que
--   valeu antes). A aba "💰 Custo por Piquete" e o DRE dependem do plano de
--   trato para custo por cabeça/dia — sem vigência, um ajuste de dieta em
--   março podia acabar sendo lido como se sempre tivesse valido, inflando
--   ou desinflando retroativamente um custo já calculado.
--
--   `nova_versao_feeding_plan`/`encerrar_feeding_plan` (database.py) seguem
--   o mesmo princípio já usado por `regras.nova_versao()`: editar no lugar
--   reescreveria o passado. A versão antiga fica com `vigente_ate` fechado;
--   a nova nasce com `vigente_de=hoje`, `vigente_ate=NULL`.
--
-- DUAS COLUNAS NOVAS, ADITIVAS
--   feeding_plans.vigente_de  — data em que esta versão do item passou a
--                                valer.
--   feeding_plans.vigente_ate — data em que parou de valer; NULL = versão
--                                corrente.
--
-- BACKFILL
--   `vigente_de` = data de `created_at` para todo registro pré-existente —
--   é o único fato que já tínhamos. `vigente_ate` fica NULL para todos,
--   inclusive os já `active=0`: não temos como saber quando pararam de
--   valer de verdade (essa informação nunca foi registrada — é exatamente
--   a lacuna que esta migration fecha para dali em diante), e inventar uma
--   data seria pior do que admitir que não sabemos. `active` continua
--   sendo, para os registros antigos, a única fonte confiável de "isto
--   está em uso hoje".
--
-- ADITIVA
--   Duas colunas novas, anuláveis, em tabela existente. Nenhuma linha é
--   apagada; nenhum valor visível de linha existente muda.
--
-- ROLLBACK
--   ALTER TABLE feeding_plans DROP COLUMN IF EXISTS vigente_de;
--   ALTER TABLE feeding_plans DROP COLUMN IF EXISTS vigente_ate;
--   -- Depois: reverter o commit e regenerar baseline e retrato.

BEGIN;

ALTER TABLE feeding_plans ADD COLUMN IF NOT EXISTS vigente_de TEXT;
ALTER TABLE feeding_plans ADD COLUMN IF NOT EXISTS vigente_ate TEXT;

COMMENT ON COLUMN feeding_plans.vigente_de IS
    'Data em que esta versão do item de trato passou a valer.';
COMMENT ON COLUMN feeding_plans.vigente_ate IS
    'Data em que parou de valer. NULL = versão corrente.';

UPDATE feeding_plans SET vigente_de = to_char(created_at, 'YYYY-MM-DD')
WHERE vigente_de IS NULL;

COMMIT;
