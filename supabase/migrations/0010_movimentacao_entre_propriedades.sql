-- ADR 0004 · etapa B6 — movimentação entre propriedades (§8)
--
-- CONTEXTO
--   Até aqui o sistema só conhecia piquete→piquete (`animal_movements`), que é
--   manejo interno e continua valendo. Esta é a movimentação com **valor
--   regulatório**: tem GTA, titular, transportador e confirmação de chegada —
--   coisas que trocar de pasto não tem.
--
--   Depende da **B4** (propriedades) e usa a validação de GTA entregue pela
--   spec 0023.
--
-- OS TRÊS NÍVEIS DO §8.4 NÃO SÃO DECORAÇÃO
--   informativo permite continuar · alerta exige confirmação e justificativa ·
--   bloqueio impede sem autorização. Confundir alerta com bloqueio trava o
--   usuário sem prova; confundir bloqueio com alerta deixa sair animal morto.
--   A gravidade é a regra, e é o que os testes verificam.
--
-- ETAPA ADITIVA
--   Duas tabelas novas. Nada existente é tocado; o rollback é `DROP`.
--
-- ROLLBACK
--   DROP TABLE movimentacao_animais;
--   DROP TABLE movimentacoes;

BEGIN;

CREATE TABLE IF NOT EXISTS movimentacoes (
    id                     text PRIMARY KEY,
    tipo                   text NOT NULL,
    propriedade_origem_id  text REFERENCES properties(id),
    propriedade_destino_id text REFERENCES properties(id),
    titular_origem_id      text REFERENCES produtores(id),
    titular_destino_id     text REFERENCES produtores(id),
    finalidade             text,
    data_prevista          text,
    data_efetiva           text,
    transportador          text,
    veiculo                text,
    gta_numero             text,
    documento_comercial    text,
    protocolo_oficial      text,
    -- rascunho | liberada | em_transito | concluida | divergente | cancelada
    status                 text NOT NULL DEFAULT 'rascunho',
    confirmacao_chegada    text,
    divergencias           text,
    anexos                 jsonb,
    justificativa          text,   -- §8.4: alerta exige confirmação
    created_at             timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_mov_status ON movimentacoes USING btree (status);
CREATE INDEX IF NOT EXISTS idx_mov_origem
    ON movimentacoes USING btree (propriedade_origem_id, data_prevista DESC);

-- Tabela própria porque um animal aparece em várias movimentações ao longo da
-- vida, e uma movimentação leva muitos animais.
CREATE TABLE IF NOT EXISTS movimentacao_animais (
    id              bigserial PRIMARY KEY,
    movimentacao_id text NOT NULL REFERENCES movimentacoes(id),
    animal_uuid     text NOT NULL REFERENCES animals(uuid),
    divergencia     text,   -- §8.2: recusa ou falta na recepção
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_mov_animal_unico
    ON movimentacao_animais USING btree (movimentacao_id, animal_uuid);
CREATE INDEX IF NOT EXISTS idx_mov_animal
    ON movimentacao_animais USING btree (animal_uuid);

COMMIT;
