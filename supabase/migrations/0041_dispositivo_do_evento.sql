-- Aparelho de origem do evento (plano de rastreabilidade, aceite offline)
--
-- CONTEXTO
--   O teste de aceite offline (#698) mostrou duas lacunas: `animal_events.origem_informacao` era
--   sempre 'web', inclusive quando a escrita vinha do app, e nenhuma escrita guardava de qual
--   aparelho ela veio. O PNIB §6.2 exige a origem da informação em todo evento, e o §14.1 pede o
--   dispositivo na trilha de auditoria (`audit_logs.dispositivo`, que já existe).
--
--   A origem passa a ser corrigida só no código (a API grava 'app'). Esta migration acrescenta o
--   aparelho ao próprio evento, para a linha do tempo do animal dizer de onde veio cada registro.
--
-- ESTRUTURA (`animal_events`, anulável; sem backfill)
--   dispositivo — identificador do aparelho que enviou a escrita: o UUID aleatório que o app gera
--                 na instalação e manda em `X-Device-Id`. Não é número de série nem dado do
--                 hardware. Nulo nos eventos anteriores a esta migration, nos do web e nos de
--                 cliente que não o envia. Não confundir com o "dispositivo" do PNIB §5, que é o
--                 brinco/tag (tabela `dispositivos`).
--
--   O gatilho de append-only recusa UPDATE e DELETE; ADD COLUMN não passa por ele.
--
-- ROLLBACK
--   ALTER TABLE public.animal_events DROP COLUMN IF EXISTS dispositivo;

BEGIN;

ALTER TABLE public.animal_events ADD COLUMN IF NOT EXISTS dispositivo text;

COMMIT;
