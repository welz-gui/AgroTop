-- Vacinação contra brucelose: o ato de vacinar e o estado do registro oficial (SDA/RS)
--
-- CONTEXTO
--   Para vacinações a partir de 01/01/2027 o atestado é emitido exclusivamente pelo SDA e o
--   lançamento vale até o quinto dia do mês seguinte (comunicado do PNCEBT/Seapi). O módulo do
--   SDA não tem API para sistemas de terceiros: o AgroTop NÃO registra nada no SDA. Ele guarda
--   o ato (quem, quando, o quê, quais animais), a ficha que o veterinário usa para lançar, e o
--   ESTADO administrativo do registro oficial, que só muda por confirmação humana.
--
-- ESTRUTURA
--   vacinacoes_brucelose          — um ato de vacinação (data, produto, lote/validade, veterinário,
--                                   propriedade) e o estado do registro oficial.
--     status_oficial   'pendente_sda' | 'registrado_sda' | 'excecao'
--     prazo_sda        quinto dia do mês seguinte; nulo para vacinação anterior a 01/01/2027,
--                      quando o lançamento no SDA ainda não é exigido
--     referencia_atestado  número/código do atestado emitido no SDA (obrigatório para
--                      'registrado_sda', informado por pessoa)
--     cancelada_*      cancelamento do ato inteiro (só antes do registro no SDA)
--   vacinacao_brucelose_animais   — os animais vacinados, com brinco, identificador oficial e
--                                   registro genealógico FOTOGRAFADOS no dia (é o que o
--                                   formulário auxiliar da Seapi pede) e a aplicação gerada.
--
--   Cada animal também ganha uma aplicação em `medications` e um evento `vacinacao_brucelose`,
--   na mesma transação, então carência, estoque, lote/validade e revisão por cancelar/corrigir
--   (0035) valem para a vacinação como para qualquer tratamento.
--
-- SEGURANÇA
--   RLS ligado e privilégios de anon/authenticated revogados na própria migration.
--
-- ROLLBACK
--   DROP TABLE IF EXISTS vacinacao_brucelose_animais;
--   DROP TABLE IF EXISTS vacinacoes_brucelose;

BEGIN;

CREATE TABLE IF NOT EXISTS vacinacoes_brucelose (
    id                    text PRIMARY KEY,
    property_id           text NOT NULL,
    vacinado_em           text NOT NULL,
    produto               text NOT NULL,
    lote_produto          text,
    validade_produto      text,
    dose                  double precision,
    unidade               text,
    via                   text,
    insumo_id             integer,
    veterinario_nome      text NOT NULL,
    veterinario_crmv      text,
    veterinario_uf        text,
    status_oficial        text NOT NULL DEFAULT 'pendente_sda',
    prazo_sda             text,
    referencia_atestado   text,
    confirmado_por        text,
    confirmado_em         text,
    justificativa_excecao text,
    registrado_por        text,
    notes                 text,
    created_at            timestamptz DEFAULT now(),
    cancelada_em          text,
    cancelada_por         text,
    motivo_cancelamento   text,
    CONSTRAINT vacinacoes_brucelose_property_fkey FOREIGN KEY (property_id) REFERENCES properties(id)
);

CREATE TABLE IF NOT EXISTS vacinacao_brucelose_animais (
    id                     bigserial PRIMARY KEY,
    vacinacao_id           text NOT NULL,
    animal_uuid            text NOT NULL,
    brinco                 text NOT NULL,
    identificador_oficial  text,
    registro_genealogico   text,
    medication_id          integer,
    CONSTRAINT vacinacao_brucelose_animais_vacinacao_fkey FOREIGN KEY (vacinacao_id) REFERENCES vacinacoes_brucelose(id),
    CONSTRAINT vacinacao_brucelose_animais_animal_fkey FOREIGN KEY (animal_uuid) REFERENCES animals(uuid),
    CONSTRAINT vacinacao_brucelose_animais_unico UNIQUE (vacinacao_id, animal_uuid)
);

CREATE INDEX IF NOT EXISTS idx_vacinacoes_brucelose_status ON vacinacoes_brucelose (status_oficial, prazo_sda);
CREATE INDEX IF NOT EXISTS idx_vacinacao_brucelose_animais_vacinacao ON vacinacao_brucelose_animais (vacinacao_id);
CREATE INDEX IF NOT EXISTS idx_vacinacao_brucelose_animais_animal ON vacinacao_brucelose_animais (animal_uuid);

ALTER TABLE vacinacoes_brucelose ENABLE ROW LEVEL SECURITY;
ALTER TABLE vacinacao_brucelose_animais ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        EXECUTE 'REVOKE ALL ON vacinacoes_brucelose FROM anon, authenticated';
        EXECUTE 'REVOKE ALL ON vacinacao_brucelose_animais FROM anon, authenticated';
        EXECUTE 'CREATE POLICY negar_anon_authenticated ON public.vacinacoes_brucelose FOR ALL TO anon, authenticated USING (false) WITH CHECK (false)';
        EXECUTE 'CREATE POLICY negar_anon_authenticated ON public.vacinacao_brucelose_animais FOR ALL TO anon, authenticated USING (false) WITH CHECK (false)';
    END IF;
END $$;

COMMIT;
