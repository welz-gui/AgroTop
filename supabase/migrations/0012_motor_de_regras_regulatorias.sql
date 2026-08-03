-- ADR 0004 · etapa B5 — motor de regras regulatórias (§11)
--
-- CONTEXTO
--   O §11 abre com a exigência que define esta etapa: **"as regras não devem
--   ficar fixadas no código-fonte"**. A portaria muda, cada UF acrescenta a sua,
--   e um frigorífico impõe protocolo próprio — codificar isso em `if`
--   significaria alterar o sistema a cada mudança normativa.
--
--   Aqui as regras são **dados**. `services/regras_regulatorias.py` só as
--   avalia. Regra nova não exige deploy.
--
-- VIGÊNCIA É A PARTE QUE SE ESQUECE
--   A regra que vale em 2027 não é a que vale em 2030 — o próprio PNIB tem
--   prazo escalonado, com identificação obrigatória para trânsito só a partir
--   de 01/01/2033. Avaliar sempre pela regra de hoje **reescreveria o passado**:
--   uma movimentação de 2027 seria julgada por norma que ainda não existia.
--
--   Por isso `data_inicial`/`data_final`, e por isso alterar uma regra cria
--   VERSÃO NOVA em vez de sobrescrever.
--
-- `ativa` SIGNIFICA APROVADA, NÃO VIGENTE
--   Quem encerra a vigência é a `data_final`. Marcar a versão antiga como
--   inativa a esconderia das consultas e o passado ficaria sem norma para
--   julgá-lo — que é exatamente o que o versionamento existe para evitar.
--
-- CONDIÇÃO É JSON COM OPERADORES FECHADOS
--   `{"campo","operador","valor"}`, com dez operadores previstos. Um avaliador
--   de expressão arbitrária vinda do banco seria porta de execução remota.
--
-- ETAPA ADITIVA · ROLLBACK: DROP TABLE regras_regulatorias;

BEGIN;

CREATE TABLE IF NOT EXISTS regras_regulatorias (
    id                   text PRIMARY KEY,
    nome                 text NOT NULL,
    descricao            text,
    fundamento           text,   -- portaria, IN, protocolo
    esfera               text NOT NULL DEFAULT 'federal',
    uf                   text,   -- NULL = vale para todas
    especie              text,
    categoria            text,
    sexo                 text,
    idade_min_meses      integer,
    idade_max_meses      integer,
    finalidade           text,
    evento_aplicacao     text,
    data_inicial         text,
    data_final           text,
    nivel                text NOT NULL DEFAULT 'informativo',
    condicao             jsonb,
    mensagem             text,
    excecoes             text,
    documentacao_exigida text,
    versao               integer NOT NULL DEFAULT 1,
    aprovado_por         text,
    ultima_revisao       text,
    ativa                integer NOT NULL DEFAULT 1,
    created_at           timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_regras_vigencia
    ON regras_regulatorias USING btree (ativa, data_inicial, data_final);
CREATE INDEX IF NOT EXISTS idx_regras_evento
    ON regras_regulatorias USING btree (evento_aplicacao, uf);

COMMIT;
