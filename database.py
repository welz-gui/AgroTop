"""
AgroTop — Camada de acesso ao banco de dados.
Funciona com SQLite (local) ou PostgreSQL/Supabase (nuvem), conforme a
variável de ambiente/segredo DATABASE_URL. Schema completo: animais,
pesagens, medicamentos, lotes, movimentações, insumos, custos, nutrição.

⚠️ Em transição (ROADMAP.md, Fase A2): as regras de negócio estão migrando para
`services/` e as consultas migrarão para `repositories/`. Este módulo segue como
fachada, reexportando o que já saiu — assim `app.py` e os testes não quebram de
uma vez. **Não adicione regra de negócio nova aqui**: ela vai para `services/`.
"""

import os
import json
import hashlib
import random
from datetime import datetime, date, timedelta
from contextlib import contextmanager
from typing import Optional
from dataclasses import dataclass

# ─── Reexportação da camada de regras (Fase A2) ──────────────────────────────
# Mantém `db.kg_to_arrobas`, `db._hash`, `db.CARCASS_YIELD` etc. funcionando para
# os chamadores existentes. Código novo deve importar de `services/` diretamente.
from services.constantes import (  # noqa: F401
    CARCASS_YIELD, KG_PER_ARROBA, UA_WEIGHT,
)
from services.zootecnia import (  # noqa: F401
    _months_between, get_age_months, get_age_category, get_age_display,
    kg_to_arrobas, estimate_weight_by_measurement, calculate_gmd_total,
)
from services.terminacao import (  # noqa: F401
    TERMINACAO_DEFAULTS, simular_terminacao,
)
from services.seguranca import (  # noqa: F401
    _hash, _is_legacy_hash, _verify_password,
)
from services.estados_animal import (  # noqa: F401
    transicao_permitida, estados_finais,
)
from services.importacao import parse_pesagens  # noqa: F401

# ─── Reexportação da camada de dados (Fase A2, fatia 3) ──────────────────────
# As consultas migraram para repositories/<agregado>.py. Reexportadas aqui para
# `app.py` e os testes seguirem funcionando durante a transição. Código novo deve
# importar do repositório diretamente. **Não adicione consulta nova aqui.**
from repositories import identificadores as identificadores  # noqa: F401
from repositories import eventos as eventos  # noqa: F401
from repositories import propriedades as propriedades  # noqa: F401
from repositories import nascimentos as nascimentos  # noqa: F401
from repositories import movimentacoes as movimentacoes  # noqa: F401
from repositories import dispositivos as dispositivos  # noqa: F401
from repositories import regras as regras  # noqa: F401
from repositories import compras as compras  # noqa: F401
from repositories.animais import uuid_de  # noqa: F401
from repositories.animais import (  # noqa: F401
    get_all_animals, get_animal, add_animal, move_animal, move_animals_bulk, get_movements, get_last_movements_bulk,
    _seed_animals,
)
from repositories.pesagens import (
    calculate_gmd_bulk,  # noqa: F401
    _weighings_by_animal, get_weighings, get_weighings_batch, add_weighing, get_all_weighings,
    calculate_gmd, get_last_estimate,
)
from repositories.sanidade import (
    get_withdrawal_end_batch,  # noqa: F401
    _medications_by_animal, get_medications, add_medication, get_withdrawal_end,
    get_protocols, add_protocol, set_protocol_active, delete_protocol,
    _protocol_pending, get_protocol_plan, apply_protocol_campaign, dose_for_animal,
)
from repositories.financeiro import (  # noqa: F401
    _costs_by_animal, get_total_cost, get_animal_costs, get_all_animal_costs,
    add_animal_cost, add_fixed_cost, get_fixed_costs, get_total_fixed_costs,
    delete_fixed_cost, get_fixed_costs_by_category, register_sale, get_sales,
    get_financial_summary, get_insumo_compras, register_death, get_deaths,
    get_mortality_stats, get_category_prices, set_category_price,
    get_expected_price_kg, expected_sale_value,
    listar_contas_receber, marcar_recebido, cancelar_receber,
    get_fixed_costs_by_lote, get_animal_costs_by_lote,
)

# ─── Camada de conexão (Fase A2) ─────────────────────────────────────────────
# Movida para repositories/conexao.py. Reexportada aqui para os chamadores atuais.
from repositories.conexao import (  # noqa: F401
    _database_url, _translate, _PGConn, _conn,
    _cache, clear_cache, _writes, configurar_sqlite,
)
import repositories.conexao as _conexao


def _quote_ident(name: str) -> str:
    """Escapes an SQL identifier (table name or column name) safely."""
    return '"' + name.replace('"', '""') + '"'


def __getattr__(name):
    """Encaminha a configuração mutável para `repositories.conexao`.

    `DB_PATH`, `DATABASE_URL`, `USE_PG` e `IntegrityError` mudam quando o backend é
    reconfigurado (testes). Se fossem reexportados por `from ... import`, ficariam
    congelados no valor do momento do import e `db.USE_PG` mentiria. Com este
    encaminhamento, o valor lido é sempre o real.

    Para ALTERAR o backend use `configurar_sqlite()` — atribuir `db.DB_PATH = x`
    não tem efeito (módulos não têm `__setattr__`), e falhar em silêncio aqui
    significaria gravar no banco errado.
    """
    if name in ("DB_PATH", "DATABASE_URL", "USE_PG", "IntegrityError"):
        return getattr(_conexao, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")








# ─── Inicialização ────────────────────────────────────────────────────────────

_SCHEMA_SQL = """
            -- Usuários
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT    UNIQUE NOT NULL,
                password_hash TEXT    NOT NULL,
                name          TEXT    NOT NULL,
                role          TEXT    NOT NULL DEFAULT 'operator'
            );

            -- Fornecedores / Origem
            CREATE TABLE IF NOT EXISTS fornecedores (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL,
                city       TEXT,
                state      TEXT DEFAULT 'MT',
                contact    TEXT,
                notes      TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );

            -- ADR 0004 · etapa B4 — §3.1: Organização → Produtor → Propriedade.
            -- O PNIB exige a hierarquia mesmo com uma fazenda só, porque o
            -- titular pode ter várias propriedades e movimentar animais entre
            -- elas (§8.1). Sem isso, `lote_id` (piquete) seria a única noção de
            -- lugar — e piquete não é estabelecimento perante o órgão.
            CREATE TABLE IF NOT EXISTS organizacoes (
                id                TEXT PRIMARY KEY,   -- uuid
                nome              TEXT NOT NULL,
                documento         TEXT,               -- CPF ou CNPJ
                responsavel_legal TEXT,
                contato           TEXT,
                status            TEXT NOT NULL DEFAULT 'ativa',
                created_at        TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS produtores (
                id                 TEXT PRIMARY KEY,  -- uuid
                organizacao_id     TEXT NOT NULL,
                nome               TEXT NOT NULL,
                documento          TEXT,
                inscricao_estadual TEXT,
                contato            TEXT,
                status             TEXT NOT NULL DEFAULT 'ativo',
                created_at         TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (organizacao_id) REFERENCES organizacoes(id)
            );

            -- §3.4: o identificador da propriedade é INTERNO E IMUTÁVEL. O
            -- `codigo_oficial` do estabelecimento pode mudar ou nem existir
            -- ainda — mesma razão de o animal ter uuid separado do brinco.
            CREATE TABLE IF NOT EXISTS properties (
                id             TEXT PRIMARY KEY,      -- uuid
                produtor_id    TEXT NOT NULL,
                nome           TEXT NOT NULL,
                codigo_oficial TEXT,
                municipio      TEXT,
                uf             TEXT,
                endereco       TEXT,
                latitude       REAL,
                longitude      REAL,
                poligono       TEXT,   -- GeoJSON; alimentado pela spec 0015
                atividade      TEXT,
                situacao       TEXT NOT NULL DEFAULT 'ativa',
                inicio         TEXT,
                encerramento   TEXT,
                created_at     TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (produtor_id) REFERENCES produtores(id)
            );
            CREATE INDEX IF NOT EXISTS idx_properties_produtor
                ON properties (produtor_id);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_properties_codigo_oficial
                ON properties (codigo_oficial) WHERE codigo_oficial IS NOT NULL;

            -- Lotes / Piquetes
            CREATE TABLE IF NOT EXISTS lotes (
                id              TEXT PRIMARY KEY,
                name            TEXT NOT NULL,
                -- §3.4: piquete pertence a uma propriedade. NOT NULL desde a
                -- B4.3 (migration 0016) — mesma ordem que funcionou no B1:
                -- escrita primeiro (add_lote sempre resolve uma propriedade
                -- padrão), restrição depois.
                property_id     TEXT NOT NULL,
                area_ha         REAL DEFAULT 0,
                capacity_ua     REAL DEFAULT 0,
                status          TEXT DEFAULT 'ativo',
                last_entry_date TEXT,
                last_exit_date  TEXT,
                notes           TEXT,
                -- Perímetro do piquete, GeoJSON — mesmo formato de
                -- properties.poligono. Alimenta services.lotacao.sobrepostos()
                -- (migration 0015; specs 0028/0043).
                poligono        TEXT,
                created_at      TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (property_id) REFERENCES properties(id)
            );

            -- ADR 0004 · etapa B5 — §11: motor de regras regulatórias.
            -- O §11 abre dizendo que "as regras não devem ficar fixadas no
            -- código-fonte". A portaria muda, cada UF acrescenta a sua, e um
            -- frigorífico impõe protocolo próprio — codificar isso em `if`
            -- significaria alterar o sistema a cada mudança normativa.
            CREATE TABLE IF NOT EXISTS regras_regulatorias (
                id                   TEXT PRIMARY KEY,   -- uuid
                nome                 TEXT NOT NULL,
                descricao            TEXT,
                fundamento           TEXT,   -- portaria, IN, protocolo
                -- federal | estadual | protocolo | interna
                esfera               TEXT NOT NULL DEFAULT 'federal',
                uf                   TEXT,   -- NULL = vale para todas
                especie              TEXT,
                categoria            TEXT,
                sexo                 TEXT,
                idade_min_meses      INTEGER,
                idade_max_meses      INTEGER,
                finalidade           TEXT,
                evento_aplicacao     TEXT,   -- movimentacao | abate | nascimento…
                -- VIGÊNCIA: a regra que vale em 2027 não é a que vale em 2030.
                -- O próprio PNIB tem prazo escalonado (identificação obrigatória
                -- para trânsito só a partir de 01/01/2033).
                data_inicial         TEXT,
                data_final           TEXT,
                -- informativo | alerta | bloqueio
                nivel                TEXT NOT NULL DEFAULT 'informativo',
                condicao             TEXT,   -- JSON: campo/operador/valor
                mensagem             TEXT,
                excecoes             TEXT,
                documentacao_exigida TEXT,
                versao               INTEGER NOT NULL DEFAULT 1,
                aprovado_por         TEXT,
                ultima_revisao       TEXT,
                ativa                INTEGER NOT NULL DEFAULT 1,
                created_at           TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_regras_vigencia
                ON regras_regulatorias (ativa, data_inicial, data_final);
            CREATE INDEX IF NOT EXISTS idx_regras_evento
                ON regras_regulatorias (evento_aplicacao, uf);

            -- ADR 0004 · etapa B7 — §5: estoque de dispositivos de identificação.
            -- O brinco é um BEM antes de ser identidade: é comprado em lote,
            -- fica em estoque, pode ser perdido ou inutilizado. Nada disso cabia
            -- em `animal_identifiers`, que registra o vínculo já feito.
            CREATE TABLE IF NOT EXISTS dispositivos (
                id                  TEXT PRIMARY KEY,   -- uuid interno
                codigo_visual       TEXT,
                codigo_eletronico   TEXT,
                -- brinco_visual | boton | conjunto | outro
                tipo                TEXT NOT NULL DEFAULT 'brinco_visual',
                tecnologia          TEXT,
                fabricante          TEXT,
                fornecedor          TEXT,
                modelo              TEXT,
                lote                TEXT,
                data_fabricacao     TEXT,
                data_aquisicao      TEXT,
                proprietario_id     TEXT,   -- produtor dono do estoque
                propriedade_destino_id TEXT,
                padrao_tecnico      TEXT,
                -- §5.2, doze estados. A máquina vive em
                -- services/estados_dispositivo.py.
                status              TEXT NOT NULL DEFAULT 'disponivel',
                data_aplicacao      TEXT,
                animal_uuid         TEXT,
                aplicador           TEXT,
                motivo_inutilizacao TEXT,
                data_baixa          TEXT,   -- devolução ou descarte
                divergencia         TEXT,   -- §5.3: visual × eletrônico
                created_at          TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (proprietario_id)        REFERENCES produtores(id),
                FOREIGN KEY (propriedade_destino_id) REFERENCES properties(id),
                FOREIGN KEY (animal_uuid)            REFERENCES animals(uuid)
            );
            -- §4.2.1: um código não pode estar ATIVO em dois dispositivos. O
            -- índice parcial permite reaproveitar o número depois da baixa,
            -- mesma lógica de `animal_identifiers`.
            CREATE UNIQUE INDEX IF NOT EXISTS idx_disp_visual_ativo
                ON dispositivos (codigo_visual)
                WHERE codigo_visual IS NOT NULL
                  AND status NOT IN ('inutilizado','devolvido','cancelado');
            CREATE INDEX IF NOT EXISTS idx_disp_status ON dispositivos (status);
            CREATE INDEX IF NOT EXISTS idx_disp_lote   ON dispositivos (lote);
            CREATE INDEX IF NOT EXISTS idx_disp_animal ON dispositivos (animal_uuid);

            -- ADR 0004 · etapa B6 — §8: movimentação entre PROPRIEDADES.
            -- Distinta de `animal_movements`, que é piquete→piquete e continua
            -- valendo para manejo interno. Esta é a movimentação com valor
            -- regulatório: tem GTA, titular, transportador e confirmação de
            -- chegada — coisas que trocar de pasto não tem.
            CREATE TABLE IF NOT EXISTS movimentacoes (
                id                     TEXT PRIMARY KEY,   -- uuid
                tipo                   TEXT NOT NULL,      -- §8.1
                propriedade_origem_id  TEXT,
                propriedade_destino_id TEXT,
                titular_origem_id      TEXT,
                titular_destino_id     TEXT,
                finalidade             TEXT,
                data_prevista          TEXT,
                data_efetiva           TEXT,
                transportador          TEXT,
                veiculo                TEXT,
                gta_numero             TEXT,
                documento_comercial    TEXT,
                protocolo_oficial      TEXT,
                -- rascunho | liberada | em_transito | concluida | cancelada
                status                 TEXT NOT NULL DEFAULT 'rascunho',
                confirmacao_chegada    TEXT,
                divergencias           TEXT,
                anexos                 TEXT,   -- JSON
                justificativa          TEXT,   -- §8.4: alerta exige confirmação
                created_at             TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (propriedade_origem_id)  REFERENCES properties(id),
                FOREIGN KEY (propriedade_destino_id) REFERENCES properties(id),
                FOREIGN KEY (titular_origem_id)      REFERENCES produtores(id),
                FOREIGN KEY (titular_destino_id)     REFERENCES produtores(id)
            );
            CREATE INDEX IF NOT EXISTS idx_mov_status ON movimentacoes (status);
            CREATE INDEX IF NOT EXISTS idx_mov_origem
                ON movimentacoes (propriedade_origem_id, data_prevista DESC);

            -- Quais animais em qual movimentação. Tabela própria porque um
            -- animal pode aparecer em várias ao longo da vida, e uma
            -- movimentação leva muitos animais.
            CREATE TABLE IF NOT EXISTS movimentacao_animais (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                movimentacao_id TEXT NOT NULL,
                animal_uuid     TEXT NOT NULL,
                divergencia     TEXT,   -- §8.2: recusa ou falta na recepção
                created_at      TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (movimentacao_id) REFERENCES movimentacoes(id),
                FOREIGN KEY (animal_uuid)     REFERENCES animals(uuid)
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_mov_animal_unico
                ON movimentacao_animais (movimentacao_id, animal_uuid);
            CREATE INDEX IF NOT EXISTS idx_mov_animal
                ON movimentacao_animais (animal_uuid);

            -- ADR 0004 · etapa B3 — §7: nascimentos e vínculo materno.
            -- O parto é entidade própria, e não um campo do animal, porque o
            -- §7.2 exige que gêmeos gerem "animais distintos ligados ao MESMO
            -- parto". Com o parto no animal, dois gêmeos teriam dois partos.
            CREATE TABLE IF NOT EXISTS partos (
                id             TEXT PRIMARY KEY,     -- uuid
                mae_uuid       TEXT NOT NULL,
                data           TEXT NOT NULL,        -- data de negócio (R5)
                hora           TEXT,
                tipo_parto     TEXT,                 -- normal | assistido | cesarea
                condicao       TEXT,                 -- nascido_vivo | natimorto
                propriedade_id TEXT,
                responsavel    TEXT,
                data_estimada  INTEGER NOT NULL DEFAULT 0,
                observacoes    TEXT,
                created_at     TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (mae_uuid)       REFERENCES animals(uuid),
                FOREIGN KEY (propriedade_id) REFERENCES properties(id)
            );
            CREATE INDEX IF NOT EXISTS idx_partos_mae ON partos (mae_uuid, data DESC);

            -- Animais
            CREATE TABLE IF NOT EXISTS animals (
                -- `id` é o número do brinco: continua único, mas deixou de ser a
                -- PK na etapa B1.7 (ADR 0004 §4.1 — identificador interno
                -- imutável e separado do brinco). As etapas B1.1-B1.6 já tinham
                -- deixado `uuid` NOT NULL/UNIQUE e migrado as 13 tabelas
                -- filhas para apontar a FK para `animals(uuid)`, nunca para
                -- `id` — esta etapa só formaliza na PK o que já era verdade.
                -- Bancos SQLite antigos não recebem a troca via ALTER (mesma
                -- limitação aceita para as FKs, dívida nº 8 do ROADMAP); só
                -- quem nasce depois desta etapa tem `uuid` como PK.
                id               TEXT UNIQUE NOT NULL,
                uuid             TEXT PRIMARY KEY NOT NULL,
                breed            TEXT NOT NULL,
                sex              TEXT NOT NULL DEFAULT 'M',
                birth_date       TEXT,
                birth_estimated  INTEGER DEFAULT 0,
                age_source       TEXT DEFAULT 'propriedade',
                nf_number        TEXT,
                gta_number       TEXT,
                entry_date       TEXT NOT NULL,
                entry_weight     REAL NOT NULL,
                current_weight   REAL NOT NULL,
                target_weight    REAL DEFAULT 500,
                status           TEXT NOT NULL DEFAULT 'ativo',
                lote_id          TEXT,
                -- §3.4 · etapa B4. NOT NULL desde a B4.3 (migration 0016) —
                -- as escritas já preenchiam antes disso (add_animal,
                -- nascimentos.registrar e o seed sempre resolvem uma
                -- propriedade padrão via _seed_hierarquia).
                property_id      TEXT NOT NULL,
                -- §4.3 · etapa B3. A propriedade de NASCIMENTO é diferente da
                -- atual: o animal se move, o lugar onde nasceu não muda.
                propriedade_nascimento_id TEXT,
                mae_uuid         TEXT,
                pai_uuid         TEXT,   -- "quando conhecido" (§4.3)
                parto_id         TEXT,   -- gêmeos compartilham (§7.2)
                peso_nascimento  REAL,
                -- nascido | comprado | transferido | importado (§4.3)
                origem           TEXT NOT NULL DEFAULT 'comprado',
                fornecedor_id    INTEGER,
                purchase_price   REAL DEFAULT 0,
                purchase_mode    TEXT DEFAULT 'cabeca',
                purchase_lot_ref TEXT,
                carcass_yield    REAL DEFAULT 0.52,
                notes            TEXT,
                created_at       TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (lote_id)       REFERENCES lotes(id),
                FOREIGN KEY (property_id)   REFERENCES properties(id),
                FOREIGN KEY (propriedade_nascimento_id) REFERENCES properties(id),
                FOREIGN KEY (mae_uuid)      REFERENCES animals(uuid),
                FOREIGN KEY (pai_uuid)      REFERENCES animals(uuid),
                FOREIGN KEY (parto_id)      REFERENCES partos(id),
                FOREIGN KEY (fornecedor_id) REFERENCES fornecedores(id)
            );

            -- Pesagens
            CREATE TABLE IF NOT EXISTS weighings (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                animal_uuid   TEXT NOT NULL,
                weight      REAL NOT NULL,
                weigh_date  TEXT NOT NULL,
                lote_id     TEXT,
                operator    TEXT,
                method      TEXT DEFAULT 'pesado',
                notes       TEXT,
                created_at  TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (animal_uuid)   REFERENCES animals(uuid)
            );

            -- Insumos (estoque)
            CREATE TABLE IF NOT EXISTS insumos (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT NOT NULL,
                category      TEXT NOT NULL DEFAULT 'medicamento',
                unit          TEXT NOT NULL DEFAULT 'ml',
                current_stock REAL NOT NULL DEFAULT 0,
                min_stock     REAL NOT NULL DEFAULT 0,
                cost_per_unit REAL DEFAULT 0,
                supplier      TEXT,
                notes         TEXT,
                created_at    TEXT DEFAULT (datetime('now','localtime'))
            );

            -- Medicamentos / Vacinas aplicados
            CREATE TABLE IF NOT EXISTS medications (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                animal_uuid         TEXT NOT NULL,
                medication_name   TEXT NOT NULL,
                dose              REAL DEFAULT 0,
                unit              TEXT DEFAULT 'ml',
                application_route TEXT DEFAULT 'Subcutânea',
                withdrawal_days   INTEGER DEFAULT 0,
                med_date          TEXT NOT NULL,
                applied_by        TEXT,
                insumo_id         INTEGER,
                notes             TEXT,
                protocol_id       INTEGER,
                created_at        TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (insumo_id) REFERENCES insumos(id),
                FOREIGN KEY (animal_uuid)   REFERENCES animals(uuid)
            );

            -- Movimentações entre lotes
            CREATE TABLE IF NOT EXISTS animal_movements (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                animal_uuid     TEXT NOT NULL,
                from_lote_id  TEXT,
                to_lote_id    TEXT NOT NULL,
                movement_date TEXT NOT NULL,
                reason        TEXT DEFAULT 'manejo',
                operator      TEXT,
                notes         TEXT,
                created_at    TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (animal_uuid)   REFERENCES animals(uuid)
            );

            -- Transações de estoque de insumos
            CREATE TABLE IF NOT EXISTS insumo_transactions (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                insumo_id        INTEGER NOT NULL,
                type             TEXT NOT NULL,
                quantity         REAL NOT NULL,
                reason           TEXT,
                animal_uuid        TEXT,   -- anulável: nem toda saída de estoque é de um animal
                transaction_date TEXT NOT NULL,
                operator         TEXT,
                notes            TEXT,
                lote_id          TEXT,
                compra_id        TEXT,   -- anulável; preenchido só quando vem de repositories.compras.registrar
                created_at       TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (insumo_id) REFERENCES insumos(id),
                FOREIGN KEY (animal_uuid)   REFERENCES animals(uuid),
                FOREIGN KEY (compra_id)   REFERENCES compras(id)
            );

            -- Compra de insumos (Trilha 3, migration 0018): cabeçalho da nota.
            -- "compra gera conta a pagar" (ROADMAP §5) — o item e a conta a
            -- pagar abaixo nascem juntos, na mesma transação de `repositories/
            -- compras.py::registrar`, nunca soltos um do outro.
            CREATE TABLE IF NOT EXISTS compras (
                id                TEXT PRIMARY KEY,   -- uuid
                fornecedor_id     INTEGER,             -- anulável: fornecedor pode não estar cadastrado
                fornecedor_nome   TEXT,
                documento_numero  TEXT,
                documento_serie   TEXT,
                data_emissao      TEXT NOT NULL,
                data_recebimento  TEXT NOT NULL,
                valor_total       REAL NOT NULL DEFAULT 0,
                operator          TEXT,
                notes             TEXT,
                created_at        TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (fornecedor_id) REFERENCES fornecedores(id)
            );

            -- Itens da compra — 1 linha por insumo da nota.
            CREATE TABLE IF NOT EXISTS compra_itens (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                compra_id      TEXT NOT NULL,
                insumo_id      INTEGER NOT NULL,
                quantidade     REAL NOT NULL,
                custo_unitario REAL NOT NULL,
                subtotal       REAL NOT NULL,
                FOREIGN KEY (compra_id) REFERENCES compras(id),
                FOREIGN KEY (insumo_id) REFERENCES insumos(id)
            );

            -- Contas a pagar — parcelas geradas por `services.compras.gerar_parcelas`.
            -- `compra_id` anulável de propósito: nem toda conta a pagar nasce de
            -- uma compra de insumo (aluguel, prestador, etc. ficam para depois,
            -- mas a coluna já não bloqueia isso).
            CREATE TABLE IF NOT EXISTS contas_pagar (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                compra_id      TEXT,
                fornecedor_nome TEXT,
                descricao      TEXT,
                valor          REAL NOT NULL,
                vencimento     TEXT NOT NULL,
                parcela_numero INTEGER NOT NULL DEFAULT 1,
                parcela_total  INTEGER NOT NULL DEFAULT 1,
                status         TEXT NOT NULL DEFAULT 'aberto',  -- aberto | pago | cancelado
                data_pagamento TEXT,
                forma_pagamento TEXT,
                operator       TEXT,
                created_at     TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (compra_id) REFERENCES compras(id)
            );

            -- Custos por animal
            CREATE TABLE IF NOT EXISTS animal_costs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                animal_uuid   TEXT NOT NULL,
                cost_type   TEXT NOT NULL DEFAULT 'operacional',
                description TEXT,
                amount      REAL NOT NULL,
                cost_date   TEXT NOT NULL,
                notes       TEXT,
                created_at  TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (animal_uuid)   REFERENCES animals(uuid)
            );

            -- Custos fixos (nível da fazenda: aluguel, salários, impostos, taxas)
            CREATE TABLE IF NOT EXISTS fixed_costs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                category    TEXT NOT NULL DEFAULT 'outro',
                description TEXT,
                amount      REAL NOT NULL,
                cost_date   TEXT NOT NULL,
                recurring   INTEGER DEFAULT 0,
                notes       TEXT,
                lote_id     TEXT,  -- centro de custo (piquete); NULL = geral da fazenda
                created_at  TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (lote_id) REFERENCES lotes(id)
            );

            -- Programação de trato/ração/mineral por piquete
            CREATE TABLE IF NOT EXISTS feeding_plans (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                lote_id      TEXT NOT NULL,
                product_name TEXT NOT NULL,
                insumo_id    INTEGER,
                quantity     REAL NOT NULL DEFAULT 0,
                unit         TEXT NOT NULL DEFAULT 'kg',
                frequency    TEXT NOT NULL DEFAULT 'diario',
                active       INTEGER DEFAULT 1,
                notes        TEXT,
                -- Vigência (Trilha 3, ROADMAP §5): "editar" um item de trato
                -- não sobrescreve — encerra esta versão (vigente_ate) e cria
                -- outra (nova_versao_feeding_plan), mesmo princípio de
                -- regras_regulatorias.nova_versao(). vigente_ate=NULL é a
                -- versão corrente do item.
                vigente_de   TEXT,
                vigente_ate  TEXT,
                created_at   TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (lote_id)   REFERENCES lotes(id),
                FOREIGN KEY (insumo_id) REFERENCES insumos(id)
            );

            -- Checagens de execução do trato (operador confirma)
            CREATE TABLE IF NOT EXISTS feeding_checks (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_id         INTEGER,
                lote_id         TEXT NOT NULL,
                check_date      TEXT NOT NULL,
                status          TEXT NOT NULL DEFAULT 'feito',
                actual_quantity REAL,
                operator        TEXT,
                notes           TEXT,
                created_at      TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (plan_id) REFERENCES feeding_plans(id),
                FOREIGN KEY (lote_id) REFERENCES lotes(id)
            );

            -- Preços esperados por categoria (idade x sexo) — apenas por kg
            CREATE TABLE IF NOT EXISTS category_prices (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                age_band       TEXT NOT NULL,
                sex            TEXT NOT NULL,
                price_per_kg   REAL DEFAULT 0,
                price_per_head REAL DEFAULT 0,
                updated_at     TEXT DEFAULT (datetime('now','localtime')),
                UNIQUE (age_band, sex)
            );

            -- Vendas (1 linha por animal; lote agrupado por lot_ref)
            CREATE TABLE IF NOT EXISTS sales (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                animal_uuid    TEXT NOT NULL,
                sale_date    TEXT NOT NULL,
                sale_type    TEXT NOT NULL DEFAULT 'abate',
                pricing_mode TEXT NOT NULL DEFAULT 'kg',
                weight_kg    REAL,
                price_per_kg REAL,
                total_value  REAL NOT NULL DEFAULT 0,
                buyer        TEXT,
                lot_ref      TEXT,
                cost_at_sale REAL DEFAULT 0,
                profit       REAL DEFAULT 0,
                operator     TEXT,
                notes        TEXT,
                a_prazo      INTEGER NOT NULL DEFAULT 0,  -- 1 = receita rastreada via contas_receber, não aqui
                created_at   TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (animal_uuid)   REFERENCES animals(uuid)
            );

            -- Contas a receber — parcelas de venda a prazo (Trilha 3, ROADMAP §5).
            -- Espelha `contas_pagar`: `lot_ref` é anulável e NÃO é FK (o mesmo texto
            -- livre que `sales.lot_ref` já usa para agrupar venda de vários animais,
            -- que por sua vez também não é chave — ver comentário de `sales` acima).
            -- Venda à vista (o padrão, sempre foi) não gera nenhuma linha aqui.
            CREATE TABLE IF NOT EXISTS contas_receber (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                lot_ref          TEXT,
                comprador        TEXT,
                descricao        TEXT,
                valor            REAL NOT NULL,
                vencimento       TEXT NOT NULL,
                parcela_numero   INTEGER NOT NULL DEFAULT 1,
                parcela_total    INTEGER NOT NULL DEFAULT 1,
                status           TEXT NOT NULL DEFAULT 'aberto',  -- aberto | recebido | cancelado
                data_recebimento TEXT,
                forma_recebimento TEXT,
                operator         TEXT,
                created_at       TEXT DEFAULT (datetime('now','localtime'))
            );

            -- Óbitos (mortalidade) com causa
            CREATE TABLE IF NOT EXISTS deaths (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                animal_uuid       TEXT NOT NULL,
                death_date      TEXT NOT NULL,
                cause           TEXT NOT NULL DEFAULT 'Desconhecida',
                lote_id         TEXT,
                weight_at_death REAL,
                cost_at_death   REAL DEFAULT 0,
                operator        TEXT,
                notes           TEXT,
                created_at      TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (animal_uuid)   REFERENCES animals(uuid)
            );

            -- Configurações gerais (chave/valor)
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            );

            -- Pluviometria (chuva medida, por piquete)
            CREATE TABLE IF NOT EXISTS pluviometria (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                read_date  TEXT NOT NULL,
                rain_mm    REAL NOT NULL DEFAULT 0,
                lote_id    TEXT,
                operator   TEXT,
                notes      TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );

            -- Fotos dos animais (imagem comprimida, com histórico)
            CREATE TABLE IF NOT EXISTS animal_photos (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                animal_uuid  TEXT NOT NULL,
                image      BLOB NOT NULL,
                mime       TEXT DEFAULT 'image/jpeg',
                taken_date TEXT NOT NULL,
                operator   TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (animal_uuid)   REFERENCES animals(uuid)
            );

            -- Protocolos sanitários (vacinação obrigatória por idade/sexo)
            CREATE TABLE IF NOT EXISTS health_protocols (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                name            TEXT NOT NULL,
                sex_target      TEXT NOT NULL DEFAULT 'ambos',
                age_min         INTEGER DEFAULT 0,
                age_max         INTEGER DEFAULT 999,
                dose_value      REAL DEFAULT 1,
                dose_ref_kg     REAL DEFAULT 0,
                dose_unit       TEXT DEFAULT 'ml',
                insumo_id       INTEGER,
                frequency       TEXT NOT NULL DEFAULT 'anual',
                withdrawal_days INTEGER DEFAULT 0,
                route           TEXT DEFAULT 'Subcutânea',
                active          INTEGER DEFAULT 1,
                notes           TEXT,
                created_at      TEXT DEFAULT (datetime('now','localtime'))
            );

            -- Índices para performance (volume futuro)
            CREATE INDEX IF NOT EXISTS idx_weighings_animal_date ON weighings (animal_uuid, weigh_date DESC);
            CREATE INDEX IF NOT EXISTS idx_medications_animal ON medications (animal_uuid);
            CREATE INDEX IF NOT EXISTS idx_medications_protocol ON medications (protocol_id);
            CREATE INDEX IF NOT EXISTS idx_animal_costs_animal ON animal_costs (animal_uuid);
            CREATE INDEX IF NOT EXISTS idx_insumo_trans_lote ON insumo_transactions (lote_id);
            CREATE INDEX IF NOT EXISTS idx_animals_status ON animals (status);
            CREATE INDEX IF NOT EXISTS idx_animal_photos_animal ON animal_photos (animal_uuid);
            CREATE INDEX IF NOT EXISTS idx_compra_itens_compra ON compra_itens (compra_id);
            CREATE INDEX IF NOT EXISTS idx_contas_pagar_status ON contas_pagar (status, vencimento);
            CREATE INDEX IF NOT EXISTS idx_contas_pagar_compra ON contas_pagar (compra_id);
            CREATE INDEX IF NOT EXISTS idx_contas_receber_status ON contas_receber (status, vencimento);
            CREATE INDEX IF NOT EXISTS idx_fixed_costs_lote ON fixed_costs (lote_id);

            -- Sessões de login persistente (cookie). Definida aqui, e só aqui:
            -- antes era criada sob demanda dentro de create_session/get_session_user/
            -- delete_session, o que deixava um banco novo sem a tabela até o 1º login.
            -- Identificadores do animal (ADR 0004 · PNIB §4.1 e §4.2).
            -- O brinco deixa de ser a identidade e vira UM identificador entre
            -- vários, com vigência própria. Trocar brinco passa a ser encerrar
            -- um registro e abrir outro — sem apagar o anterior (§4.2.3).
            CREATE TABLE IF NOT EXISTS animal_identifiers (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                animal_uuid    TEXT NOT NULL,
                tipo           TEXT NOT NULL,
                valor          TEXT NOT NULL,
                -- 'ativo' | 'removido' | 'inutilizado'
                status         TEXT NOT NULL DEFAULT 'ativo',
                aplicado_em    TEXT,
                removido_em    TEXT,
                motivo_remocao TEXT,
                aplicado_por   TEXT,
                created_at     TEXT DEFAULT (datetime('now','localtime'))
            );
            -- §4.2.1 e §4.2.2: um código oficial ou RFID não pode estar ATIVO em
            -- dois animais. O índice parcial permite o mesmo valor no histórico
            -- (status='removido'), que é o que preserva a rastreabilidade.
            CREATE UNIQUE INDEX IF NOT EXISTS idx_ident_ativo_unico
                ON animal_identifiers (tipo, valor) WHERE status = 'ativo';
            CREATE INDEX IF NOT EXISTS idx_ident_animal
                ON animal_identifiers (animal_uuid);

            -- ADR 0004 · etapa B2 — §6: histórico de eventos do animal.
            -- APPEND-ONLY. Evento confirmado nunca é apagado nem sobrescrito;
            -- correção gera um NOVO evento apontando para o anterior (§6.3).
            -- Os gatilhos abaixo impõem isso — comentário não impõe nada.
            --
            -- Adoção incremental (ADR 0004): por ora os eventos são REGISTRADOS
            -- junto das operações atuais. Derivar o estado do animal a partir
            -- deles é passo posterior; fazer as duas coisas de uma vez seria
            -- reescrever o sistema num salto.
            CREATE TABLE IF NOT EXISTS animal_events (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                animal_uuid         TEXT NOT NULL,
                tipo                TEXT NOT NULL,
                -- §6.2 separa QUANDO ACONTECEU de QUANDO FOI REGISTRADO: em
                -- evento regulatório a diferença entre os dois é auditável.
                -- Emenda à R5: aqui vai data/hora COM fuso, não data de negócio.
                ocorrido_em         TEXT NOT NULL,
                registrado_em       TEXT NOT NULL,
                propriedade_id      TEXT,     -- chega na etapa B4
                local_interno       TEXT,
                responsavel         TEXT,
                usuario_registro    TEXT,
                origem_informacao   TEXT,     -- web | app | integracao | importacao
                latitude            REAL,
                longitude           REAL,
                observacoes         TEXT,
                documento           TEXT,
                anexos              TEXT,     -- JSON; jsonb no Postgres
                -- ⚠️ LEGADAS (ADR 0005). Ficam porque o §6.2 as prevê, mas são o
                -- estado de NASCIMENTO do evento, congelado — a linha é imutável,
                -- então nunca mudam. Quem responde "já foi comunicado?" é
                -- `evento_sincronizacao`, logo abaixo. Não use em predicado novo.
                status_sincronizacao TEXT NOT NULL DEFAULT 'pendente',
                identificador_oficial TEXT,   -- devolvido pelo sistema oficial
                versao              INTEGER NOT NULL DEFAULT 1,
                evento_anterior_id  INTEGER,  -- correção/estorno aponta para o original
                justificativa       TEXT,
                created_at          TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (animal_uuid)        REFERENCES animals(uuid),
                FOREIGN KEY (evento_anterior_id) REFERENCES animal_events(id)
            );
            CREATE INDEX IF NOT EXISTS idx_eventos_animal
                ON animal_events (animal_uuid, ocorrido_em DESC);
            CREATE INDEX IF NOT EXISTS idx_eventos_tipo
                ON animal_events (tipo, ocorrido_em DESC);
            CREATE INDEX IF NOT EXISTS idx_eventos_sincronizacao
                ON animal_events (status_sincronizacao)
                WHERE status_sincronizacao <> 'sincronizado';

            -- §6.3 na marra. Sem estes gatilhos, "append-only" é só uma frase.
            CREATE TRIGGER IF NOT EXISTS trg_eventos_sem_update
            BEFORE UPDATE ON animal_events
            BEGIN
                SELECT RAISE(ABORT,
                    'animal_events e append-only (PNIB 6.3): gere um evento de correcao');
            END;
            CREATE TRIGGER IF NOT EXISTS trg_eventos_sem_delete
            BEFORE DELETE ON animal_events
            BEGIN
                SELECT RAISE(ABORT,
                    'animal_events e append-only (PNIB 6.3): evento nao se apaga');
            END;

            -- ADR 0005 — §10.3: a fila de sincronização com os sistemas oficiais.
            --
            -- Está FORA de `animal_events` de propósito. O §10.2 manda manter a
            -- camada de integração fora do núcleo; o §10.3 pede catorze
            -- situações, não uma bandeira; e uma exceção no gatilho só se
            -- escreveria, no SQLite, como `BEFORE UPDATE OF <as outras 19
            -- colunas>` — lista de permissão por omissão, em que toda coluna
            -- futura nasceria mutável. Ver docs/adr/0005-fila-de-sincronizacao.md.
            --
            -- Append-only também: tentativa de envio que aconteceu não
            -- desacontece. A situação vigente de um par (evento, sistema) é a
            -- ÚLTIMA linha; não há coluna "atual" para divergir do histórico.
            CREATE TABLE IF NOT EXISTS evento_sincronizacao (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                evento_id      INTEGER NOT NULL,
                -- §10.1 prevê vários destinos. 'oficial' é neutro de propósito:
                -- não presume qual sistema virá primeiro (§23).
                sistema        TEXT NOT NULL DEFAULT 'oficial',
                situacao       TEXT NOT NULL,   -- §10.3, validada em services/
                protocolo      TEXT,            -- §10.4 registro manual
                mensagem       TEXT,            -- retorno do sistema
                observacoes    TEXT,            -- texto de quem operou
                anexos         TEXT,            -- JSON; jsonb no Postgres
                usuario        TEXT,
                conferido_por  TEXT,            -- §10.4 dupla conferência
                ocorrido_em    TEXT NOT NULL,
                registrado_em  TEXT NOT NULL,
                created_at     TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (evento_id) REFERENCES animal_events(id)
            );
            CREATE INDEX IF NOT EXISTS idx_evsinc_evento
                ON evento_sincronizacao (evento_id, sistema, id DESC);
            CREATE INDEX IF NOT EXISTS idx_evsinc_situacao
                ON evento_sincronizacao (situacao);

            CREATE TRIGGER IF NOT EXISTS trg_evsinc_sem_update
            BEFORE UPDATE ON evento_sincronizacao
            BEGIN
                SELECT RAISE(ABORT,
                    'evento_sincronizacao e append-only (PNIB 10.2): registre outra transicao');
            END;
            CREATE TRIGGER IF NOT EXISTS trg_evsinc_sem_delete
            BEFORE DELETE ON evento_sincronizacao
            BEGIN
                SELECT RAISE(ABORT,
                    'evento_sincronizacao e append-only (PNIB 10.2): transicao nao se apaga');
            END;

            -- ADR 0004 · etapa B2 — §14.1: trilha de auditoria.
            -- Responde "quem mudou o quê, quando, de onde e com que autorização".
            -- É o destino definitivo da justificativa que hoje vai para
            -- `animals.notes` nas transições sensíveis de status.
            CREATE TABLE IF NOT EXISTS audit_logs (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario            TEXT,
                ocorrido_em        TEXT NOT NULL,
                dispositivo        TEXT,
                ip                 TEXT,
                acao               TEXT NOT NULL,
                entidade           TEXT,      -- tabela ou agregado afetado
                entidade_id        TEXT,
                registro_anterior  TEXT,      -- JSON; jsonb no Postgres
                registro_posterior TEXT,
                motivo             TEXT,
                autorizacao        TEXT,      -- quem autorizou a ação sensível
                origem             TEXT NOT NULL DEFAULT 'web',
                protocolo_externo  TEXT,
                created_at         TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_audit_ocorrido
                ON audit_logs (ocorrido_em DESC);
            CREATE INDEX IF NOT EXISTS idx_audit_entidade
                ON audit_logs (entidade, entidade_id);

            -- Auditoria também não se reescreve: seria o primeiro alvo de quem
            -- quisesse encobrir uma ação.
            CREATE TRIGGER IF NOT EXISTS trg_audit_sem_update
            BEFORE UPDATE ON audit_logs
            BEGIN
                SELECT RAISE(ABORT, 'audit_logs e append-only (PNIB 14.1)');
            END;
            CREATE TRIGGER IF NOT EXISTS trg_audit_sem_delete
            BEFORE DELETE ON audit_logs
            BEGIN
                SELECT RAISE(ABORT, 'audit_logs e append-only (PNIB 14.1)');
            END;

            CREATE TABLE IF NOT EXISTS sessions (
                token      TEXT PRIMARY KEY,
                user_id    INTEGER,
                expires_at TEXT
            );

            CREATE TABLE IF NOT EXISTS api_refresh_tokens (
                token      TEXT PRIMARY KEY,
                user_id    INTEGER NOT NULL,
                expires_at TEXT NOT NULL,
                revoked    INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            CREATE INDEX IF NOT EXISTS idx_api_refresh_tokens_user
                ON api_refresh_tokens (user_id);

            CREATE TABLE IF NOT EXISTS api_idempotency_keys (
                idempotency_key TEXT PRIMARY KEY,
                endpoint        TEXT NOT NULL,
                status_code     INTEGER NOT NULL,
                response_body   TEXT NOT NULL,
                created_at      TEXT DEFAULT (datetime('now','localtime'))
            );
"""

_INICIALIZADO_EM = None


def init_db(forcar: bool = False) -> None:
    """Cria/atualiza o schema e semeia os dados obrigatórios.

    `app.py` chama isto a cada rerun do Streamlit, e antes da guarda abaixo
    todo clique pagava 1 conexão + 11 queries de seed e backfill (~0,45 s em
    produção). O trabalho é idempotente, mas repeti-lo não tem valor: uma vez
    por processo e por banco basta.

    `forcar=True` ignora a guarda — é como os testes de idempotência conferem
    que rodar duas vezes de verdade não duplica nem altera nada.
    """
    global _INICIALIZADO_EM
    alvo = _conexao.DATABASE_URL or _conexao.DB_PATH
    if not forcar and _INICIALIZADO_EM == alvo:
        return

    with _conn() as con:
        if not _conexao.USE_PG:
            con.executescript(_SCHEMA_SQL)
        _migrate(con)
        _seed_users(con)
        _seed_fornecedores(con)
        # B4.3 — a hierarquia (§3) precisa existir ANTES do seed de lotes e
        # animais, para eles nascerem já com `property_id` preenchido, em vez
        # de depender do backfill abaixo — que só cobre banco com EXATAMENTE
        # uma propriedade (`_backfill_property_id`), e que em SQLite roda
        # tarde demais: a coluna é `NOT NULL` desde a migration 0016, e o
        # próprio `INSERT` do seed já falharia antes de o backfill ser
        # alcançado.
        propriedade_padrao_id = propriedades._seed_hierarquia(con)
        _seed_lotes(con, propriedade_padrao_id)
        _seed_animals(con, propriedade_padrao_id)
        _seed_insumos(con)
        # Depois dos seeds: animais semeados também precisam de UUID.
        _backfill_uuids(con)
        _backfill_animal_uuid(con)
        _backfill_identificadores(con)
        # Safety net só para banco EXISTENTE, criado antes da B4 — o seed
        # novo acima já não deixa NULL nenhum para este backfill cobrir.
        propriedades._backfill_property_id(con)

    # Só depois de tudo dar certo: um init que falhou no meio precisa rodar de novo.
    _INICIALIZADO_EM = alvo


def _migrate(con) -> None:
    """Adiciona colunas novas a bancos SQLite criados por versões anteriores.
    No Postgres o schema já vem completo pela migração."""
    if _conexao.USE_PG:
        return
    cols = {r["name"] for r in con.execute("PRAGMA table_info(animals)").fetchall()}
    # ADR 0004 etapa B1.2 — espelho do uuid nas tabelas filhas.
    for _t in ("weighings", "medications", "animal_costs", "animal_movements",
               "animal_photos", "deaths", "sales", "insumo_transactions"):
        qt = _quote_ident(_t)
        _c = {r["name"] for r in con.execute(f"PRAGMA table_info({qt})").fetchall()}
        if "animal_uuid" not in _c:
            con.execute(f"ALTER TABLE {qt} ADD COLUMN animal_uuid TEXT")

    if "uuid" not in cols:
        # ADR 0004 etapa 1. Sem UNIQUE aqui: o ALTER do SQLite não aceita, e a
        # restrição vem do CREATE TABLE em bancos novos.
        con.execute("ALTER TABLE animals ADD COLUMN uuid TEXT")
    if "birth_estimated" not in cols:
        con.execute("ALTER TABLE animals ADD COLUMN birth_estimated INTEGER DEFAULT 0")
    if "age_source" not in cols:
        con.execute("ALTER TABLE animals ADD COLUMN age_source TEXT DEFAULT 'propriedade'")
    if "nf_number" not in cols:
        con.execute("ALTER TABLE animals ADD COLUMN nf_number TEXT")
    if "gta_number" not in cols:
        con.execute("ALTER TABLE animals ADD COLUMN gta_number TEXT")
    if "purchase_mode" not in cols:
        con.execute("ALTER TABLE animals ADD COLUMN purchase_mode TEXT DEFAULT 'cabeca'")
    if "purchase_lot_ref" not in cols:
        con.execute("ALTER TABLE animals ADD COLUMN purchase_lot_ref TEXT")
    wcols = {r["name"] for r in con.execute("PRAGMA table_info(weighings)").fetchall()}
    if "method" not in wcols:
        con.execute("ALTER TABLE weighings ADD COLUMN method TEXT DEFAULT 'pesado'")
    tcols = {r["name"] for r in con.execute("PRAGMA table_info(insumo_transactions)").fetchall()}
    if "lote_id" not in tcols:
        con.execute("ALTER TABLE insumo_transactions ADD COLUMN lote_id TEXT")
    if "compra_id" not in tcols:
        # Migration 0020 — liga insumo_transactions à compra que a gerou, para o
        # fluxo de caixa não contar a mesma compra duas vezes (competência via
        # insumo_transactions, caixa via contas_pagar).
        con.execute("ALTER TABLE insumo_transactions ADD COLUMN compra_id TEXT")
    mcols = {r["name"] for r in con.execute("PRAGMA table_info(medications)").fetchall()}
    if "protocol_id" not in mcols:
        con.execute("ALTER TABLE medications ADD COLUMN protocol_id INTEGER")
    lcols = {r["name"] for r in con.execute("PRAGMA table_info(lotes)").fetchall()}
    if "poligono" not in lcols:
        # Migration 0015 — perímetro do piquete, destrava services.lotacao.sobrepostos().
        con.execute("ALTER TABLE lotes ADD COLUMN poligono TEXT")
    scols = {r["name"] for r in con.execute("PRAGMA table_info(sales)").fetchall()}
    if "a_prazo" not in scols:
        # Migration 0020 — mesma razão: distingue venda cujo caixa é rastreado
        # via contas_receber (a_prazo=1) da venda à vista (caixa imediato).
        con.execute("ALTER TABLE sales ADD COLUMN a_prazo INTEGER NOT NULL DEFAULT 0")
    fccols = {r["name"] for r in con.execute("PRAGMA table_info(fixed_costs)").fetchall()}
    if "lote_id" not in fccols:
        # Migration 0021 — centro de custo (piquete) do custo fixo; NULL
        # continua válido e significa "geral da fazenda", não "esqueceram".
        con.execute("ALTER TABLE fixed_costs ADD COLUMN lote_id TEXT")
    fpcols = {r["name"] for r in con.execute("PRAGMA table_info(feeding_plans)").fetchall()}
    if "vigente_de" not in fpcols:
        # Migration 0022 — vigência do item de trato. Backfill honesto: só
        # sabemos a data de criação, não quando uma versão antiga terminou
        # de valer (essa informação nunca existiu) — por isso vigente_ate
        # fica NULL para todo registro pré-existente, e `active` continua a
        # única forma de saber se um item pré-migration está em uso hoje.
        con.execute("ALTER TABLE feeding_plans ADD COLUMN vigente_de TEXT")
        con.execute("ALTER TABLE feeding_plans ADD COLUMN vigente_ate TEXT")
        con.execute(
            "UPDATE feeding_plans SET vigente_de=date(created_at) WHERE vigente_de IS NULL")

# ─── Seeds ────────────────────────────────────────────────────────────────────

def _backfill_uuids(con) -> int:
    """Gera UUID para animais que ainda não têm (ADR 0004, etapa 1).

    Idempotente: roda a cada `init_db()` e só toca em linhas com `uuid` nulo.
    Existe porque a coluna nasceu depois dos dados — animais cadastrados antes
    da migração não teriam identificador interno.
    """
    from repositories.animais import novo_uuid

    sem = con.execute("SELECT id FROM animals WHERE uuid IS NULL").fetchall()
    if sem:
        updates = [(novo_uuid(), row["id"]) for row in sem]
        con.executemany("UPDATE animals SET uuid=? WHERE id=?", updates)
    return len(sem)


def _colunas(con, tabela: str) -> set:
    """Nomes das colunas de uma tabela, **nos dois bancos**.

    `PRAGMA table_info` é sintaxe exclusiva do SQLite: no Postgres o driver
    devolve erro de sintaxe. Este auxiliar existe porque essa diferença já
    derrubou a produção uma vez — a suíte roda inteira com `AGROTOP_FORCE_SQLITE`
    e não enxerga o caminho Postgres.
    """
    if _conexao.USE_PG:
        rows = con.execute(
            "SELECT column_name AS name FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name=?", (tabela,)
        ).fetchall()
    else:
        rows = con.execute(f"PRAGMA table_info({_quote_ident(tabela)})").fetchall()
    return {r["name"] for r in rows}


def _backfill_animal_uuid(con) -> int:
    """Espelha `animals.uuid` nas filhas que AINDA tenham `animal_id` (etapa B1.2).

    Só faz sentido em banco que ainda não passou pela etapa B1.6: a partir dela
    `animal_id` não existe mais, e não há de onde derivar o uuid. Por isso a
    conferência de colunas antes — a função vira no-op num banco já migrado, em
    vez de estourar. Mantida porque bancos antigos ainda chegam aqui pelo
    `_migrate`.
    """
    total = 0
    for t in ("weighings", "medications", "animal_costs", "animal_movements",
              "animal_photos", "deaths", "sales", "insumo_transactions"):
        if "animal_id" not in _colunas(con, t):
            continue
        qt = _quote_ident(t)
        cur = con.execute(
            f"UPDATE {qt} SET animal_uuid = ("
            f"  SELECT a.uuid FROM animals a WHERE a.id = {qt}.animal_id"
            f") WHERE animal_uuid IS NULL AND animal_id IS NOT NULL"
        )
        total += getattr(cur, "rowcount", 0) or 0
    return total


def _backfill_identificadores(con) -> int:
    """Migra o brinco atual (`animals.id`) para `animal_identifiers` (etapa B1.3).

    O número que hoje é a PK passa a existir também como identificador de tipo
    `manejo`, vigente. Não remove nada de `animals` — as duas representações
    convivem até a etapa 6.

    Idempotente: só insere para quem ainda não tem um `manejo` ativo.
    """
    faltando = con.execute(
        "SELECT a.uuid, a.id FROM animals a "
        "WHERE a.uuid IS NOT NULL AND NOT EXISTS ("
        "  SELECT 1 FROM animal_identifiers i "
        "  WHERE i.animal_uuid = a.uuid AND i.tipo = 'manejo' AND i.status = 'ativo')"
    ).fetchall()
    for row in faltando:
        con.execute(
            "INSERT INTO animal_identifiers "
            "(animal_uuid,tipo,valor,status,aplicado_por) "
            "VALUES(?,'manejo',?,'ativo','migração ADR 0004')",
            (row["uuid"], row["id"]),
        )
    return len(faltando)


def _seed_users(con):
    """Cria os usuários iniciais APENAS numa instalação nova (tabela vazia).

    O guard é por tabela vazia, não por username: antes, checar `username`
    fazia com que apagar o usuário `admin` o ressuscitasse com a senha padrão
    na próxima inicialização — uma porta aberta num app público.
    Para recuperar acesso perdido use `tools/gerar_hash_senha.py`.
    """
    if con.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
        return

    import secrets
    import sys

    admin_pass = os.environ.get("AGROTOP_ADMIN_PASSWORD")
    if not admin_pass:
        admin_pass = secrets.token_urlsafe(12)
        print(f"ATENÇÃO: Senha gerada para o usuário 'admin': {admin_pass}", file=sys.stderr)

    op_pass = os.environ.get("AGROTOP_OP_PASSWORD")
    if not op_pass:
        op_pass = secrets.token_urlsafe(12)
        print(f"ATENÇÃO: Senha gerada para o usuário 'op1': {op_pass}", file=sys.stderr)

    for u, p, n, r in [
        ("admin", admin_pass, "Administrador",  "admin"),
        ("op1",   op_pass,    "Operador Campo", "operator"),
    ]:
        con.execute(
            "INSERT INTO users (username,password_hash,name,role) VALUES(?,?,?,?)",
            (u, _hash(p), n, r),
        )


def _seed_fornecedores(con):
    if con.execute("SELECT COUNT(*) FROM fornecedores").fetchone()[0]:
        return
    for name, city, state in [
        ("Fazenda Santa Fé",   "Cuiabá",       "MT"),
        ("Agro Pantanal Ltda", "Corumbá",      "MS"),
        ("Rancho Verde",       "Uberlândia",   "MG"),
        ("Estância Boa Vista", "Campo Grande", "MS"),
    ]:
        con.execute(
            "INSERT INTO fornecedores (name,city,state) VALUES(?,?,?)",
            (name, city, state),
        )


def _seed_lotes(con, property_id: str = None):
    if con.execute("SELECT COUNT(*) FROM lotes").fetchone()[0]:
        return
    for lid, name, area, cap, status in [
        ("P01", "Piquete Central",   15.0, 25.0, "ativo"),
        ("P02", "Piquete Norte",     12.0, 20.0, "ativo"),
        ("P03", "Piquete Sul",       18.0, 30.0, "ativo"),
        ("P04", "Piquete Leste",     10.0, 15.0, "descanso"),
        ("CRL", "Curral Principal",   0.5,  0.0, "ativo"),
    ]:
        con.execute(
            "INSERT INTO lotes (id,name,area_ha,capacity_ua,status,property_id) "
            "VALUES(?,?,?,?,?,?)",
            (lid, name, area, cap, status, property_id),
        )




def _seed_insumos(con):
    if con.execute("SELECT COUNT(*) FROM insumos").fetchone()[0]:
        return
    items = [
        ("Ivermectina 1%",   "medicamento", "ml",    800.0, 100.0, 0.15),
        ("Vacina FMD",       "vacina",      "dose",  150.0,  30.0, 3.50),
        ("Closantel 10%",    "medicamento", "ml",    400.0,  80.0, 0.28),
        ("Vitamina ADE",     "medicamento", "ml",    500.0,  80.0, 0.09),
        ("Oxitetraciclina",  "medicamento", "ml",     80.0,  50.0, 0.45),
        ("Sal Mineral",      "mineral",     "kg",   1200.0, 200.0, 4.80),
        ("Ração Engorda",    "racao",       "kg",   4500.0, 800.0, 1.25),
        ("Vermífugo Oral",   "medicamento", "ml",     45.0,  60.0, 0.35),
        ("Silagem de Milho", "trato",       "ton",    85.0,  15.0, 320.00),
        ("Massa de Soja",    "trato",       "ton",    12.0,   5.0, 1150.00),
        ("Bagaço de Laranja","trato",       "ton",    30.0,   8.0, 180.00),
    ]
    for name, cat, unit, stock, min_s, cpu in items:
        con.execute(
            """INSERT INTO insumos (name,category,unit,current_stock,min_stock,cost_per_unit)
               VALUES(?,?,?,?,?,?)""",
            (name, cat, unit, stock, min_s, cpu),
        )

# ─── Utilidades ───────────────────────────────────────────────────────────────









# Rótulos das faixas etárias (registro por idade)

# Formas de definição da idade
AGE_SOURCES = {
    "propriedade": "Nascido na propriedade (data exata)",
    "estimado":    "Nascimento estimado (mês aproximado)",
    "operador":    "Idade definida pelo operador",
    "nf_gta":      "Idade da NF / GTA",
}




def birth_date_from_age(age_months: int, ref_date: Optional[date] = None) -> str:
    """Calcula a data de nascimento retroativa a partir de uma idade em meses.
    Usada quando o operador ou a NF/GTA informam a idade em vez da data."""
    ref = ref_date or date.today()
    total = ref.year * 12 + (ref.month - 1) - int(age_months)
    year, month = divmod(total, 12)
    month += 1
    # dia 15 como referência média do mês (nascimento estimado)
    day = min(15, 28)
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return date(year, month, 1).isoformat()











# ─── Autenticação ─────────────────────────────────────────────────────────────

def verify_login(username: str, password: str) -> Optional[dict]:
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM users WHERE username=?", (username,)
        ).fetchone()
    if not row or not _verify_password(password, row["password_hash"]):
        return None
    # Migração automática: atualiza hash legado (SHA-256) para PBKDF2
    if _is_legacy_hash(row["password_hash"]):
        try:
            with _conn() as con:
                con.execute("UPDATE users SET password_hash=? WHERE id=?",
                            (_hash(password), row["id"]))
            clear_cache()
        except Exception:
            pass
    user = dict(row)
    user.pop("password_hash", None)   # nunca expõe o hash
    return user

# ─── Sessões persistentes (login lembrado) ───────────────────────────────────

def create_session(user_id: int, days: int = 7) -> str:
    """Cria um token de sessão e retorna-o. Usado para manter o login ao recarregar."""
    import secrets
    token = secrets.token_urlsafe(24)
    expires = (datetime.now() + timedelta(days=days)).isoformat()
    with _conn() as con:
        if _conexao.USE_PG:
            con.execute(
                "INSERT INTO sessions (token,user_id,expires_at) VALUES(?,?,?) "
                "ON CONFLICT (token) DO UPDATE SET user_id=EXCLUDED.user_id, expires_at=EXCLUDED.expires_at",
                (token, user_id, expires),
            )
        else:
            con.execute(
                "INSERT OR REPLACE INTO sessions (token,user_id,expires_at) VALUES(?,?,?)",
                (token, user_id, expires),
            )
    return token


def get_session_user(token: str) -> Optional[dict]:
    """Retorna o usuário associado a um token de sessão válido (não expirado)."""
    if not token:
        return None
    with _conn() as con:
        row = con.execute(
            "SELECT user_id, expires_at FROM sessions WHERE token=?", (token,)
        ).fetchone()
        if not row:
            return None
        try:
            if datetime.fromisoformat(row["expires_at"]) < datetime.now():
                con.execute("DELETE FROM sessions WHERE token=?", (token,))
                return None
        except (ValueError, TypeError):
            return None
        u = con.execute(
            "SELECT id, username, name, role FROM users WHERE id=?", (row["user_id"],)
        ).fetchone()
    return dict(u) if u else None


def delete_session(token: str) -> None:
    if not token:
        return
    with _conn() as con:
        con.execute("DELETE FROM sessions WHERE token=?", (token,))

# ─── Gestão de Usuários ──────────────────────────────────────────────────────

def get_all_users() -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT id, username, name, role FROM users ORDER BY role, username"
        ).fetchall()
    return [dict(r) for r in rows]


def get_user(user_id: int) -> Optional[dict]:
    with _conn() as con:
        row = con.execute(
            "SELECT id, username, name, role FROM users WHERE id=?", (user_id,)
        ).fetchone()
    return dict(row) if row else None


def username_exists(username: str, exclude_id: Optional[int] = None) -> bool:
    with _conn() as con:
        if exclude_id is not None:
            row = con.execute(
                "SELECT 1 FROM users WHERE username=? AND id<>?", (username, exclude_id)
            ).fetchone()
        else:
            row = con.execute(
                "SELECT 1 FROM users WHERE username=?", (username,)
            ).fetchone()
    return row is not None


@_writes
def add_user(username: str, password: str, name: str, role: str = "operator") -> None:
    with _conn() as con:
        con.execute(
            "INSERT INTO users (username,password_hash,name,role) VALUES(?,?,?,?)",
            (username, _hash(password), name, role),
        )


@_writes
def update_user(user_id: int, name: str, role: str,
                new_password: Optional[str] = None) -> None:
    """Atualiza nome e papel; se new_password for informado, redefine a senha."""
    with _conn() as con:
        if new_password:
            con.execute(
                "UPDATE users SET name=?, role=?, password_hash=? WHERE id=?",
                (name, role, _hash(new_password), user_id),
            )
        else:
            con.execute(
                "UPDATE users SET name=?, role=? WHERE id=?",
                (name, role, user_id),
            )


@_writes
def update_username(user_id: int, new_username: str) -> None:
    with _conn() as con:
        con.execute("UPDATE users SET username=? WHERE id=?", (new_username, user_id))


@_writes
def delete_user(user_id: int) -> None:
    with _conn() as con:
        con.execute("DELETE FROM users WHERE id=?", (user_id,))


def count_admins() -> int:
    with _conn() as con:
        row = con.execute("SELECT COUNT(*) as n FROM users WHERE role='admin'").fetchone()
    return int(row["n"])

# ─── Animais ──────────────────────────────────────────────────────────────────







# Um status do sistema vira um tipo de evento do §6.1. Onde não há correspondente
# exato, `mudanca_categoria` é o genérico previsto pela portaria.
_EVENTO_POR_STATUS = {
    "vendido": "venda",
    "morto": "morte",
    "abatido": "abate",
    "ativo": "mudanca_categoria",
    "carencia": "manejo_sanitario",
}


@_writes
def update_animal_status(animal_id: str, status: str, *,
                         tem_autorizacao: bool = False,
                         justificativa: str = "",
                         operador: str = "") -> dict:
    """Muda o status do animal **passando pela máquina de estados** (PNIB §14.2).

    Este é o único funil de mudança de status, então a regra vale para todos os
    chamadores. Transições cotidianas (ativo→vendido, carencia→ativo) seguem
    livres; sair de um estado final — ressuscitar um animal vendido, morto ou
    abatido — exige `tem_autorizacao` **e** justificativa.

    Devolve dicionário em vez de levantar: a interface precisa do motivo para
    mostrar ao usuário, e quem ignora o retorno mantém o comportamento anterior
    nas transições livres.

    A justificativa vai para `audit_logs` (§14.1) e a mudança vira um evento em
    `animal_events` (§6) — as duas append-only. Até a etapa B2 isso era anexado
    a `animals.notes`, que funcionava mas não era consultável nem protegido
    contra reescrita.
    """
    with _conn() as con:
        row = con.execute(
            "SELECT status, uuid FROM animals WHERE id=?", (animal_id,)
        ).fetchone()
    if row is None:
        return {"ok": False, "motivo": f"Animal {animal_id} não encontrado."}

    atual = row["status"]
    veredito = transicao_permitida(atual, status, tem_autorizacao=tem_autorizacao)
    if not veredito["permitida"]:
        return {"ok": False, "de": atual, "para": status, **veredito}

    if veredito["exige_justificativa"] and not justificativa.strip():
        return {"ok": False, "de": atual, "para": status, **veredito,
                "motivo": "Justificativa obrigatória para esta transição."}

    with _conn() as con:
        con.execute("UPDATE animals SET status=? WHERE id=?", (status, animal_id))

    # Auditoria e evento vêm DEPOIS de a escrita dar certo: registrar uma
    # mudança que não aconteceu é pior do que não registrar nada.
    eventos.auditar(
        "mudanca_status_animal",
        usuario=operador,
        entidade="animals", entidade_id=animal_id,
        registro_anterior={"status": atual},
        registro_posterior={"status": status},
        motivo=justificativa.strip(),
        autorizacao=operador if veredito["exige_autorizacao"] else "",
    )
    if row["uuid"]:
        eventos.registrar(
            row["uuid"], _EVENTO_POR_STATUS.get(status, "mudanca_categoria"),
            usuario_registro=operador,
            observacoes=f"{atual} → {status}",
            justificativa=justificativa.strip(),
        )
    return {"ok": True, "de": atual, "para": status, **veredito}


@_writes
def update_animal_age(animal_id: str, birth_date: str,
                      birth_estimated: int, age_source: str) -> None:
    """Atualiza a definição de idade de um animal existente."""
    with _conn() as con:
        con.execute(
            "UPDATE animals SET birth_date=?, birth_estimated=?, age_source=? WHERE id=?",
            (birth_date or None, int(birth_estimated), age_source, animal_id),
        )

# ─── Pesagens ────────────────────────────────────────────────────────────────



WEIGH_METHODS = {
    "pesado":   "Pesado na balança",
    "estimado": "Estimado pelo operador",
    "medicao":  "Estimado por medição (fita/fórmula)",
}











# ─── Medicamentos ─────────────────────────────────────────────────────────────




# ─── Lotes / Piquetes ────────────────────────────────────────────────────────

@_cache
def get_all_lotes() -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            """SELECT l.*,
                      COUNT(a.id) as animal_count,
                      SUM(a.current_weight) / 450.0 as total_ua
               FROM lotes l
               LEFT JOIN animals a ON a.lote_id=l.id AND a.status='ativo'
               GROUP BY l.id ORDER BY l.id""",
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        if d.get("total_ua") is not None:
            d["total_ua"] = round(float(d["total_ua"]), 2)
        out.append(d)
    return out


def get_lote(lote_id: str) -> Optional[dict]:
    with _conn() as con:
        row = con.execute("SELECT * FROM lotes WHERE id=?", (lote_id,)).fetchone()
    return dict(row) if row else None


@_writes
def add_lote(lote_id, name, area_ha, capacity_ua, notes="",
             property_id=None) -> None:
    """Cria um piquete. Sem `property_id`, assume a propriedade padrão (§3.4).

    Assumir é aceitável enquanto existe uma propriedade só. Com várias, a
    interface tem de perguntar — piquete atribuído à propriedade errada é erro
    de localização, e localização errada num sistema de rastreabilidade é pior
    que localização ausente.
    """
    with _conn() as con:
        if property_id is None:
            row = con.execute(
                "SELECT id FROM properties ORDER BY created_at LIMIT 1").fetchone()
            property_id = row["id"] if row else None
        con.execute(
            "INSERT INTO lotes (id,name,property_id,area_ha,capacity_ua,notes) "
            "VALUES(?,?,?,?,?,?)",
            (lote_id, name, property_id, area_ha, capacity_ua, notes),
        )


@_writes
def set_lote_poligono(lote_id: str, poligono_geojson: Optional[str]) -> bool:
    """Grava o perímetro do piquete (migration 0015) e deriva `area_ha` dele.

    ROADMAP Trilha 2: "área calculada, não digitada" — mesmo princípio já
    usado na tela de Propriedades, agora também na escrita do piquete, não
    só na exibição. Perímetro válido recalcula `area_ha` na mesma escrita;
    `None` apaga o desenho e preserva o último `area_ha` como fallback
    manual — regra explícita da Trilha 2: piquete sem geometria continua
    funcionando como hoje.
    """
    from services.geometria import area_hectares

    area_calculada = None
    if poligono_geojson:
        try:
            geo = json.loads(poligono_geojson)
            anel = [tuple(v) for v in geo["coordinates"][0]]
            area_calculada = round(area_hectares(anel), 2)
        except (ValueError, KeyError, TypeError, IndexError):
            area_calculada = None

    with _conn() as con:
        if area_calculada is not None:
            cur = con.execute(
                "UPDATE lotes SET poligono=?, area_ha=? WHERE id=?",
                (poligono_geojson, area_calculada, lote_id))
        else:
            cur = con.execute(
                "UPDATE lotes SET poligono=? WHERE id=?", (poligono_geojson, lote_id))
        return cur.rowcount > 0



# ─── Insumos / Estoque ───────────────────────────────────────────────────────

@_cache
def get_all_insumos() -> list[dict]:
    with _conn() as con:
        rows = con.execute("SELECT * FROM insumos ORDER BY category, name").fetchall()
    return [dict(r) for r in rows]


@_writes
def add_insumo_entry(insumo_id: int, quantity: float, cost_per_unit: float,
                     operator: str = "") -> None:
    """Registra entrada de insumo, atualizando o custo por **média ponderada**.

    Antes desta mudança o custo unitário era simplesmente sobrescrito pelo da
    última entrada: comprar 10 kg a R$ 5 com 1.000 kg a R$ 2 em estoque fazia
    todo o saldo passar a valer R$ 5/kg, inflando custo de trato e margem.

    Ver docs/adr/0003-custo-medio-ponderado.md — a decisão é **não-retroativa**:
    vale para entradas novas, e o histórico já lançado permanece como está.
    """
    from services.estoque import custo_medio_ponderado

    with _conn() as con:
        today_str = date.today().isoformat()
        atual = con.execute(
            "SELECT current_stock, cost_per_unit FROM insumos WHERE id=?", (insumo_id,)
        ).fetchone()
        novo_custo = custo_medio_ponderado(
            float(atual["current_stock"] or 0), float(atual["cost_per_unit"] or 0),
            float(quantity), float(cost_per_unit),
        ) if atual else cost_per_unit

        con.execute(
            "UPDATE insumos SET current_stock=current_stock+?, cost_per_unit=? WHERE id=?",
            (quantity, novo_custo, insumo_id),
        )
        con.execute(
            """INSERT INTO insumo_transactions
               (insumo_id,type,quantity,reason,transaction_date,operator)
               VALUES(?,?,?,?,?,?)""",
            (insumo_id, "entrada", quantity, "compra", today_str, operator),
        )


@_writes
def add_new_insumo(name, category, unit, initial_stock, min_stock, cost_per_unit) -> None:
    with _conn() as con:
        con.execute(
            "INSERT INTO insumos (name,category,unit,current_stock,min_stock,cost_per_unit) VALUES(?,?,?,?,?,?)",
            (name, category, unit, initial_stock, min_stock, cost_per_unit),
        )

# ─── Custos por Animal ───────────────────────────────────────────────────────






# ─── Custos Fixos (nível da fazenda) ─────────────────────────────────────────

FIXED_COST_CATEGORIES = [
    "Aluguel de pastagem",
    "Salários",
    "Bonificação de funcionários",
    "Impostos",
    "Taxas",
    "Energia / Combustível",
    "Manutenção",
    "Outro",
]











# ─── Programação de Trato / Ração / Mineral ──────────────────────────────────

FEEDING_FREQUENCIES = {"diario": "Diário", "semanal": "Semanal", "mensal": "Mensal"}
FEEDING_CHECK_STATUS = {"feito": "Feito", "parcial": "Parcial", "nao_feito": "Não feito"}

# Fatores de conversão para a unidade base de cada família (peso→kg, volume→litro)
_UNIT_FACTORS = {
    # peso (base: kg)
    "ton": ("peso", 1000.0), "t": ("peso", 1000.0),
    "kg": ("peso", 1.0),
    "g": ("peso", 0.001),
    # volume (base: litro)
    "litro": ("volume", 1.0), "l": ("volume", 1.0),
    "ml": ("volume", 0.001),
}


def convert_quantity(qty: float, from_unit: str, to_unit: str) -> Optional[float]:
    """Converte uma quantidade entre unidades compatíveis (kg↔ton↔g, litro↔ml).
    Retorna None se as unidades forem incompatíveis (ex.: kg → saco)."""
    if qty is None:
        return None
    fu, tu = (from_unit or "").lower().strip(), (to_unit or "").lower().strip()
    if fu == tu:
        return qty
    fi, ti = _UNIT_FACTORS.get(fu), _UNIT_FACTORS.get(tu)
    if not fi or not ti or fi[0] != ti[0]:
        return None  # incompatível ou desconhecida
    # qty * (fator_origem / fator_destino)
    return qty * fi[1] / ti[1]


@_writes
def add_feeding_plan(lote_id, product_name, quantity, unit, frequency,
                     insumo_id=None, notes="") -> None:
    with _conn() as con:
        con.execute(
            """INSERT INTO feeding_plans
               (lote_id,product_name,insumo_id,quantity,unit,frequency,notes,
                vigente_de,vigente_ate)
               VALUES(?,?,?,?,?,?,?,?,NULL)""",
            (lote_id, product_name, insumo_id or None, quantity, unit, frequency, notes,
             date.today().isoformat()),
        )


@_writes
def nova_versao_feeding_plan(plan_id: int, *, quantity=None, unit=None,
                             frequency=None, insumo_id=None, notes=None) -> dict:
    """Altera um item de trato criando OUTRA VERSÃO — nunca sobrescrevendo.

    Mesmo princípio de `regras.nova_versao()`: editar no lugar reescreveria
    o histórico de custo. `services.dieta`/`_nutricao_custo_por_piquete`
    olham o plano de HOJE; se um trato reduzido em março passasse a valer
    também para fevereiro, o custo por cabeça/dia de fevereiro mudaria
    silenciosamente num relatório que o produtor já usou para decidir algo.

    Campos não informados (`None`) herdam da versão atual. Só é permitido
    versionar um item ainda vigente (`vigente_ate IS NULL`).
    """
    with _conn() as con:
        atual = con.execute(
            "SELECT * FROM feeding_plans WHERE id=?", (plan_id,)).fetchone()
        if atual is None:
            return {"ok": False, "erro": "Item de trato não encontrado."}
        if atual["vigente_ate"] is not None:
            return {"ok": False, "erro": "Esta versão já está encerrada."}

        hoje = date.today()
        ontem = (hoje - timedelta(days=1)).isoformat()

        con.execute(
            "UPDATE feeding_plans SET vigente_ate=?, active=0 WHERE id=?",
            (ontem, plan_id))
        con.execute(
            """INSERT INTO feeding_plans
               (lote_id,product_name,insumo_id,quantity,unit,frequency,notes,
                active,vigente_de,vigente_ate)
               VALUES(?,?,?,?,?,?,?,1,?,NULL)""",
            (atual["lote_id"], atual["product_name"],
             insumo_id if insumo_id is not None else atual["insumo_id"],
             quantity if quantity is not None else atual["quantity"],
             unit or atual["unit"], frequency or atual["frequency"],
             notes if notes is not None else atual["notes"],
             hoje.isoformat()))
    return {"ok": True}


@_writes
def encerrar_feeding_plan(plan_id: int) -> dict:
    """Encerra a vigência de um item de trato — o piquete parou de receber
    isso, ponto final. Diferente de `delete_feeding_plan`: a linha continua
    existindo, então o custo já calculado com base nela permanece
    reconstruível. É esta função, não a exclusão, que a tela usa para
    'remover' um item do plano de trato."""
    with _conn() as con:
        atual = con.execute(
            "SELECT vigente_ate FROM feeding_plans WHERE id=?", (plan_id,)).fetchone()
        if atual is None:
            return {"ok": False, "erro": "Item de trato não encontrado."}
        if atual["vigente_ate"] is not None:
            return {"ok": False, "erro": "Já está encerrado."}
        con.execute(
            "UPDATE feeding_plans SET vigente_ate=?, active=0 WHERE id=?",
            (date.today().isoformat(), plan_id))
    return {"ok": True}


@_cache
def get_feeding_plan_historico(lote_id: str) -> list[dict]:
    """Todas as versões (vigentes e encerradas) dos itens de trato de um
    piquete, mais recentes primeiro — a linha do tempo completa da dieta."""
    with _conn() as con:
        rows = con.execute(
            """SELECT p.*, i.name as insumo_name FROM feeding_plans p
               LEFT JOIN insumos i ON i.id=p.insumo_id
               WHERE p.lote_id=?
               ORDER BY p.product_name, p.vigente_de DESC, p.id DESC""",
            (lote_id,)).fetchall()
    return [dict(r) for r in rows]


@_cache
def get_feeding_plans(lote_id: Optional[str] = None,
                      active_only: bool = True) -> list[dict]:
    sql = ("SELECT p.*, l.name as lote_name, i.name as insumo_name "
           "FROM feeding_plans p "
           "LEFT JOIN lotes l ON l.id=p.lote_id "
           "LEFT JOIN insumos i ON i.id=p.insumo_id WHERE 1=1")
    args: list = []
    if active_only:
        sql += " AND p.active=1"
    if lote_id:
        sql += " AND p.lote_id=?"; args.append(lote_id)
    sql += " ORDER BY p.lote_id, p.product_name"
    with _conn() as con:
        return [dict(r) for r in con.execute(sql, args).fetchall()]


@_writes
def set_feeding_plan_active(plan_id: int, active: int) -> None:
    with _conn() as con:
        con.execute("UPDATE feeding_plans SET active=? WHERE id=?", (int(active), plan_id))


@_writes
def delete_feeding_plan(plan_id: int) -> None:
    with _conn() as con:
        con.execute("DELETE FROM feeding_plans WHERE id=?", (plan_id,))


@_writes
def add_feeding_check(plan_id, lote_id, check_date, status,
                      actual_quantity=None, operator="", notes="",
                      deduct_stock=False, insumo_id=None,
                      quantity_unit="kg") -> None:
    with _conn() as con:
        con.execute(
            """INSERT INTO feeding_checks
               (plan_id,lote_id,check_date,status,actual_quantity,operator,notes)
               VALUES(?,?,?,?,?,?,?)""",
            (plan_id, lote_id, check_date, status, actual_quantity, operator, notes),
        )
        # Baixa opcional no estoque quando o trato é confirmado
        if deduct_stock and insumo_id and actual_quantity and status != "nao_feito":
            ins = con.execute(
                "SELECT unit FROM insumos WHERE id=?", (insumo_id,)
            ).fetchone()
            stock_unit = ins["unit"] if ins else quantity_unit
            # Converte a quantidade aplicada (unidade do plano) para a unidade do estoque
            deduct = convert_quantity(actual_quantity, quantity_unit, stock_unit)
            if deduct is None:
                deduct = actual_quantity   # unidades incompatíveis: baixa direta
            con.execute(
                "UPDATE insumos SET current_stock = MAX(0, current_stock - ?) WHERE id=?",
                (deduct, insumo_id),
            )
            con.execute(
                """INSERT INTO insumo_transactions
                   (insumo_id,type,quantity,reason,transaction_date,operator,lote_id)
                   VALUES(?,?,?,?,?,?,?)""",
                (insumo_id, "saida", deduct, "trato_lote", check_date, operator, lote_id),
            )


def get_feeding_checks(lote_id: Optional[str] = None,
                       start_date: Optional[str] = None,
                       end_date: Optional[str] = None) -> list[dict]:
    sql = ("SELECT c.*, l.name as lote_name, p.product_name "
           "FROM feeding_checks c "
           "LEFT JOIN lotes l ON l.id=c.lote_id "
           "LEFT JOIN feeding_plans p ON p.id=c.plan_id WHERE 1=1")
    args: list = []
    if lote_id:
        sql += " AND c.lote_id=?"; args.append(lote_id)
    if start_date:
        sql += " AND c.check_date >= ?"; args.append(start_date)
    if end_date:
        sql += " AND c.check_date <= ?"; args.append(end_date)
    sql += " ORDER BY c.check_date DESC, c.id DESC"
    with _conn() as con:
        return [dict(r) for r in con.execute(sql, args).fetchall()]


def get_plan_check_for_date(plan_id: int, check_date: str) -> Optional[dict]:
    """Retorna a checagem de um plano numa data específica, se existir."""
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM feeding_checks WHERE plan_id=? AND check_date=? ORDER BY id DESC LIMIT 1",
            (plan_id, check_date),
        ).fetchone()
    return dict(row) if row else None


def _period_key(freq: str, d: date) -> str:
    """Identificador do período atual conforme a frequência do plano."""
    if freq == "semanal":
        y, w, _ = d.isocalendar()
        return f"{y}-W{w:02d}"
    if freq == "mensal":
        return f"{d.year}-{d.month:02d}"
    return d.isoformat()   # diário (ou padrão)


def get_pending_feedings(ref_date: Optional[date] = None) -> list[dict]:
    """Retorna os planos de nutrição ativos e, para cada um, se já foi confirmado
    no período atual (dia/semana/mês). Só há planos para piquetes cadastrados pelo
    admin — piquetes sem plano não entram na lista."""
    ref = ref_date or date.today()
    plans = get_feeding_plans(active_only=True)
    if not plans:
        return []

    plan_ids = [p["id"] for p in plans]
    last_checks = {}

    with _conn() as con:
        chunk_size = 900
        for i in range(0, len(plan_ids), chunk_size):
            chunk = plan_ids[i:i+chunk_size]
            placeholders = ",".join("?" * len(chunk))
            query = f"SELECT plan_id, MAX(check_date) as check_date FROM feeding_checks WHERE plan_id IN ({placeholders}) GROUP BY plan_id"
            rows = con.execute(query, chunk).fetchall()
            for row in rows:
                last_checks[row["plan_id"]] = row["check_date"]

        result = []
        for p in plans:
            done = False
            last_date = last_checks.get(p["id"])
            if last_date:
                try:
                    ld = datetime.strptime(last_date, "%Y-%m-%d").date()
                    done = _period_key(p["frequency"], ld) == _period_key(p["frequency"], ref)
                except (ValueError, TypeError):
                    done = False
            result.append({**p, "done_this_period": done, "last_check": last_date})
    return result

# ─── Preços por Categoria (valor esperado por kg) ────────────────────────────

SALE_TYPES = {"abate": "Abate (frigorífico)", "criacao": "Criação (reprodução/recria)"}
PRICING_MODES = {"kg": "Por kg (peso × preço)",
                 "cabeca": "Por cabeça (valor fechado)",
                 "lote": "Por lote fechado (valor único do grupo)"}











# ─── Vendas ──────────────────────────────────────────────────────────────────




# ─── Mortalidade ─────────────────────────────────────────────────────────────

DEATH_CAUSES = [
    "Doença", "Predação", "Acidente", "Intoxicação (planta tóxica)",
    "Cobra/Picada", "Parto/Distocia", "Raio", "Afogamento",
    "Timpanismo", "Desnutrição", "Desconhecida", "Outra",
]





# ─── Administração: edição direta de tabelas ─────────────────────────────────

ADMIN_TABLES = [
    "animals", "weighings", "medications", "insumos", "lotes",
    "fornecedores", "animal_costs", "fixed_costs", "insumo_transactions",
    "animal_movements", "feeding_plans", "feeding_checks",
    "category_prices", "sales", "deaths", "settings", "health_protocols",
    "pluviometria", "users",
]


def admin_table_info(table: str) -> tuple[list[str], str]:
    """Retorna (colunas, coluna_pk) de uma tabela permitida."""
    if table not in ADMIN_TABLES:
        raise ValueError(f"Tabela não permitida: {table}")
    with _conn() as con:
        if _conexao.USE_PG:
            cols = [r["name"] for r in con.execute(
                "SELECT column_name AS name FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name=? ORDER BY ordinal_position",
                (table,)).fetchall()]
            pkrows = con.execute(
                "SELECT a.attname AS name FROM pg_index i "
                "JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum = ANY(i.indkey) "
                "WHERE i.indrelid = (?::regclass) AND i.indisprimary", (table,)).fetchall()
            pk = pkrows[0]["name"] if pkrows else (cols[0] if cols else "id")
        else:
            info = con.execute(f"PRAGMA table_info({_quote_ident(table)})").fetchall()
            cols = [r["name"] for r in info]
            pk = next((r["name"] for r in info if r["pk"]), cols[0])
    return cols, pk


def admin_get_rows(table: str) -> list[dict]:
    if table not in ADMIN_TABLES:
        raise ValueError(f"Tabela não permitida: {table}")
    _, pk = admin_table_info(table)
    with _conn() as con:
        qt = _quote_ident(table)
        qpk = _quote_ident(pk)
        rows = con.execute(f"SELECT * FROM {qt} ORDER BY {qpk}").fetchall()
    return [dict(r) for r in rows]


@_writes
def admin_apply_changes(table: str, updates: list[dict],
                        inserts: list[dict], delete_pks: list) -> dict:
    """Aplica alterações vindas do editor. `updates` e `inserts` são dicts de
    coluna→valor (updates precisam conter a PK). Retorna contagem por operação."""
    if table not in ADMIN_TABLES:
        raise ValueError(f"Tabela não permitida: {table}")
    cols, pk = admin_table_info(table)
    valid = set(cols)
    n_upd = n_ins = n_del = 0
    with _conn() as con:
        qt = _quote_ident(table)
        qpk = _quote_ident(pk)
        # Exclusões
        for pkv in delete_pks:
            # Seguro: qt e qpk são validados via ADMIN_TABLES e PRAGMA e scappados via _quote_ident.
            con.execute(f"DELETE FROM {qt} WHERE {qpk}=?", (pkv,))  # nosec B608
            n_del += 1
        # Atualizações
        for row in updates:
            pkv = row.get(pk)
            fields = {k: v for k, v in row.items() if k in valid and k != pk}
            if not fields:
                continue
            sets = ", ".join(f"{_quote_ident(k)}=?" for k in fields)
            # Seguro: qt, sets e qpk são validados (k in valid) e scappados via _quote_ident.
            con.execute(f"UPDATE {qt} SET {sets} WHERE {qpk}=?",  # nosec B608
                        (*fields.values(), pkv))
            n_upd += 1
        # Inserções
        for row in inserts:
            fields = {k: v for k, v in row.items()
                      if k in valid and v is not None and str(v) != ""}
            if not fields:
                continue
            placeholders = ", ".join("?" for _ in fields)
            cols_str = ", ".join(_quote_ident(k) for k in fields)
            # Seguro: qt e cols_str são validados (k in valid) e scappados via _quote_ident.
            con.execute(
                f"INSERT INTO {qt} ({cols_str}) VALUES ({placeholders})",  # nosec B608
                tuple(fields.values()))
            n_ins += 1
    return {"updated": n_upd, "inserted": n_ins, "deleted": n_del}


# ─── Fornecedores ────────────────────────────────────────────────────────────

def get_all_fornecedores() -> list[dict]:
    with _conn() as con:
        rows = con.execute("SELECT * FROM fornecedores ORDER BY name").fetchall()
    return [dict(r) for r in rows]


@_writes
def add_fornecedor(name, city, state, contact="", notes="") -> None:
    with _conn() as con:
        con.execute(
            "INSERT INTO fornecedores (name,city,state,contact,notes) VALUES(?,?,?,?,?)",
            (name, city, state, contact, notes),
        )


def get_fornecedor_ranking() -> list[dict]:
    """Ranking ampliado por fornecedor de origem, sobre **todo o histórico**
    (animais ativos, vendidos e mortos):
      - GMD médio (dos animais com pesagem suficiente)
      - taxa de mortalidade (mortos ÷ total do fornecedor)
      - custo por @ produzida (custo acumulado ÷ arrobas de carcaça ganhas)
    Peso final por animal: peso registrado no óbito, se houver; senão o peso atual.
    """
    animals = get_all_animals(status=None)  # todos os status
    with _conn() as con:
        drows = con.execute(
            "SELECT a.id AS animal_id, d.weight_at_death FROM deaths d "
            "JOIN animals a ON a.uuid=d.animal_uuid").fetchall()
    death_w = {r["animal_id"]: r["weight_at_death"] for r in drows}

    agg: dict[str, dict] = {}
    costs = _costs_by_animal()
    for a in animals:
        fname = a.get("fornecedor_name") or "Não informado"
        d = agg.setdefault(fname, {"n": 0, "ativos": 0, "vendidos": 0, "mortos": 0,
                                   "gmds": [], "custo_total": 0.0, "arrobas": 0.0})
        d["n"] += 1
        status = a.get("status")
        if status == "morto":
            d["mortos"] += 1
        elif status == "vendido":
            d["vendidos"] += 1
        else:
            d["ativos"] += 1

        g = calculate_gmd(a["id"])
        if g is not None:
            d["gmds"].append(g)

        d["custo_total"] += costs.get(a["id"], 0.0)

        peso_final = death_w.get(a["id"]) or a.get("current_weight") or 0
        ganho = peso_final - (a.get("entry_weight") or 0)
        if ganho > 0:
            d["arrobas"] += ganho * CARCASS_YIELD / KG_PER_ARROBA

    out = []
    for fname, d in agg.items():
        n, gmds = d["n"], d["gmds"]
        out.append({
            "fornecedor": fname, "n": n,
            "ativos": d["ativos"], "vendidos": d["vendidos"], "mortos": d["mortos"],
            "gmd_medio": round(sum(gmds)/len(gmds), 3) if gmds else 0.0,
            "taxa_mortalidade": round(d["mortos"]/n*100, 1) if n else 0.0,
            "custo_total": round(d["custo_total"], 2),
            "arrobas_produzidas": round(d["arrobas"], 2),
            "custo_por_arroba": round(d["custo_total"]/d["arrobas"], 2) if d["arrobas"] > 0 else 0.0,
        })
    return sorted(out, key=lambda x: -x["gmd_medio"])

# ─── Alertas ─────────────────────────────────────────────────────────────────

@_cache
def get_alert_animals() -> dict:
    # "ativo" + "carencia": animais em carência saem do status "ativo" (ver
    # refresh_carencia_status), mas continuam no rebanho em manejo — é
    # justamente a categoria "Em Carência" abaixo que precisa enxergá-los.
    # Sem isso, a categoria nunca retorna nada (bug real, não achado da spec).
    animals = get_all_animals(status="ativo") + get_all_animals(status="carencia")
    today   = date.today()
    sumidos, carencia_active, prontos = [], [], []

    all_weighings = _weighings_by_animal()
    all_medications = _medications_by_animal()

    withdrawal_ends = {}
    for animal_id, meds in all_medications.items():
        latest = None
        for r in meds:
            if not r["withdrawal_days"]:
                continue
            try:
                end = datetime.strptime(r["med_date"], "%Y-%m-%d").date() + timedelta(days=r["withdrawal_days"])
                if end > today and (latest is None or end > latest):
                    latest = end
            except ValueError:
                pass
        withdrawal_ends[animal_id] = latest

    for a in animals:
        animal_id = a["id"]
        # Sumidos: sem pesagem nos últimos 30 dias
        ws = all_weighings.get(animal_id, [])
        if ws:
            last_w = datetime.strptime(ws[0]["weigh_date"], "%Y-%m-%d").date()
            if (today - last_w).days > 30:
                sumidos.append({**a, "days_since_weighing": (today - last_w).days})

        # Em carência ativa
        end = withdrawal_ends.get(animal_id)
        if end and end >= today:
            carencia_active.append({**a, "withdrawal_end": end.isoformat(),
                                    "days_remaining": (end - today).days})

        # Prontos para abate
        target = a.get("target_weight") or 500
        if a["current_weight"] >= target and not end:
            prontos.append({**a, "arrobas": kg_to_arrobas(a["current_weight"])})

    return {"sumidos": sumidos, "carencia": carencia_active, "prontos": prontos}


@_cache
def check_low_stock() -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM insumos WHERE current_stock <= min_stock ORDER BY name"
        ).fetchall()
    return [dict(r) for r in rows]

# ─── KPIs e Estatísticas ─────────────────────────────────────────────────────

@dataclass
class AnimalStats:
    total: int = 0
    avg_weight: float = 0.0
    avg_gmd: float = 0.0
    total_kg: float = 0.0
    males: int = 0
    females: int = 0
    total_ua: float = 0.0
    total_area: float = 0.0
    lotacao_ua_ha: float = 0.0
    arrobas_prod: float = 0.0

@_cache
def get_rebanho_stats() -> AnimalStats:
    animals = get_all_animals()
    lotes   = get_all_lotes()
    if not animals:
        return AnimalStats()

    weights = [a["current_weight"] for a in animals]
    gains   = [a["current_weight"] - a["entry_weight"] for a in animals]
    gmds    = [g for g in (calculate_gmd(a["id"]) for a in animals) if g is not None]

    total_ua    = sum(w / UA_WEIGHT for w in weights)
    total_area  = sum(l["area_ha"] for l in lotes if l["area_ha"] and l["status"] == "ativo")
    lotacao     = round(total_ua / total_area, 2) if total_area else 0
    arrobas_prod = sum(kg_to_arrobas(g) for g in gains if g > 0)

    return AnimalStats(
        total=len(animals),
        avg_weight=round(sum(weights) / len(weights), 1),
        avg_gmd=round(sum(gmds) / len(gmds), 3) if gmds else 0,
        total_kg=round(sum(weights), 0),
        males=sum(1 for a in animals if a["sex"] == "M"),
        females=sum(1 for a in animals if a["sex"] == "F"),
        total_ua=round(total_ua, 1),
        total_area=total_area,
        lotacao_ua_ha=lotacao,
        arrobas_prod=round(arrobas_prod, 1),
    )




def refresh_carencia_status() -> None:
    """Atualiza automaticamente o status de animais cuja carência expirou."""
    today = date.today()
    animals = get_all_animals(status="carencia")
    for a in animals:
        end = get_withdrawal_end(a["id"])
        if end is None or end < today:
            update_animal_status(a["id"], "ativo")

# ─── Configurações (chave/valor) ─────────────────────────────────────────────

def get_setting(key: str, default=None):
    with _conn() as con:
        row = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


@_writes
def set_setting(key: str, value) -> None:
    with _conn() as con:
        if _conexao.USE_PG:
            con.execute(
                "INSERT INTO settings (key,value) VALUES(?,?) "
                "ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value",
                (key, str(value)),
            )
        else:
            con.execute("INSERT OR REPLACE INTO settings (key,value) VALUES(?,?)",
                        (key, str(value)))

# ─── Desempenho (GMD, projeção de abate, comparativo por piquete) ────────────

def get_gmd_target() -> float:
    try:
        return float(get_setting("gmd_meta", "0.500"))
    except (TypeError, ValueError):
        return 0.5


def get_low_performance(meta: Optional[float] = None) -> list[dict]:
    """Animais com GMD abaixo da meta."""
    meta = meta if meta is not None else get_gmd_target()
    out = []
    for a in get_all_animals():
        g = calculate_gmd(a["id"])
        if g is not None and g < meta:
            out.append({**a, "gmd": g})
    return sorted(out, key=lambda x: x["gmd"])


def projecao_abate(animal: dict) -> dict:
    """Dias e data estimada para atingir o peso-alvo, pelo GMD atual.

    Delega a `services.projecao.projetar_abate` (R8) — antes essa conta era
    reimplementada aqui com `round()` em vez de `ceil()`, o que podia
    arredondar dias PARA BAIXO (ex.: falta 10 kg a 3 kg/dia são 3,33 dias;
    `round` virava 3, `ceil` — o certo, já que dia fracionado não conta —
    vira 4), estimando o abate um dia antes do possível. Corrigido em
    2026-08-14, ligando o service que nunca tinha sido chamado.
    """
    from services.projecao import projetar_abate

    g = calculate_gmd(animal["id"])
    target = animal.get("target_weight") or 500
    falta = round(max(0.0, target - animal["current_weight"]), 1)
    r = projetar_abate(animal["current_weight"], target, g, date.today().isoformat())
    return {"dias": r["dias_restantes"], "data": r["data_prevista"], "gmd": g,
            "falta": falta, "situacao": r["situacao"]}


def projecao_abate_bulk(animals: list[dict]) -> dict:
    """
    Calcula a projeção de abate e o GMD de vida em massa apenas para
    os animais passados na lista. Resolve o problema N+1 delegando o
    cálculo vetorizado (por animal_id) ao repositório e serviços.

    A conta de dias/data delega a `services.projecao.projetar_abate` (R8) —
    mesma correção de arredondamento de `projecao_abate()` acima.
    """
    from repositories.pesagens import calculate_gmd_bulk
    from services.zootecnia import calculate_gmd_total_bulk
    from services.projecao import projetar_abate

    animal_ids = [a["id"] for a in animals]
    gmds = calculate_gmd_bulk(animal_ids)
    gmd_totals = calculate_gmd_total_bulk(animals)
    hoje_iso = date.today().isoformat()

    result = {}
    for a in animals:
        aid = a["id"]
        g = gmds.get(aid)
        target = a.get("target_weight") or 500
        falta = round(max(0.0, target - a["current_weight"]), 1)
        r = projetar_abate(a["current_weight"], target, g, hoje_iso)
        p = {"dias": r["dias_restantes"], "data": r["data_prevista"], "gmd": g,
             "falta": falta, "situacao": r["situacao"]}
        result[aid] = {"projecao": p, "gmd_total": gmd_totals.get(aid)}

    return result


def get_performance_by_lote() -> list[dict]:
    """Por piquete: GMD médio × investimento em nutrição → custo por GMD."""
    animals = get_all_animals()
    lotes = {l["id"]: l for l in get_all_lotes()}
    with _conn() as con:
        rows = con.execute(
            "SELECT t.lote_id AS lid, COALESCE(SUM(t.quantity*i.cost_per_unit),0) AS c "
            "FROM insumo_transactions t JOIN insumos i ON i.id=t.insumo_id "
            "WHERE t.reason='trato_lote' AND t.lote_id IS NOT NULL GROUP BY t.lote_id"
        ).fetchall()
    nut = {r["lid"]: float(r["c"]) for r in rows}

    by_lote: dict = {}
    for a in animals:
        by_lote.setdefault(a.get("lote_id"), []).append(a)

    result = []
    for lid, ans in by_lote.items():
        if not lid:
            continue
        gmds = [g for g in (calculate_gmd(a["id"]) for a in ans) if g is not None]
        gmd_med = sum(gmds) / len(gmds) if gmds else 0.0
        n = len(ans)
        custo_nut = nut.get(lid, 0.0)
        custo_por_animal = custo_nut / n if n else 0.0
        result.append({
            "lote_id":  lid,
            "lote_name": (lotes.get(lid) or {}).get("name", lid),
            "n":        n,
            "gmd_medio": round(gmd_med, 3),
            "custo_nutricao": round(custo_nut, 2),
            "custo_nut_por_animal": round(custo_por_animal, 2),
            # R$ de nutrição por animal para cada kg/dia de GMD (eficiência)
            "custo_por_gmd": round(custo_por_animal / gmd_med, 2) if gmd_med > 0 else 0.0,
        })
    return sorted(result, key=lambda x: -x["gmd_medio"])

# ─── Simulador de terminação (pasto × semi × confinamento) ───────────────────

# Cenários-padrão editáveis (o usuário calibra na tela e salva em settings).




def get_terminacao_cenarios() -> list[dict]:
    """Cenários salvos pelo usuário (settings JSON) ou os defaults."""
    raw = get_setting("terminacao_cenarios")
    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, list) and data:
                return data
        except (ValueError, TypeError):
            pass
    return [dict(c) for c in TERMINACAO_DEFAULTS]


def set_terminacao_cenarios(cenarios: list[dict]) -> None:
    set_setting("terminacao_cenarios", json.dumps(cenarios))

# ─── Pluviometria (chuva medida por piquete) ─────────────────────────────────

@_writes
def add_rain(read_date: str, rain_mm: float, lote_id: Optional[str] = None,
             operator: str = "", notes: str = "") -> None:
    with _conn() as con:
        con.execute(
            "INSERT INTO pluviometria (read_date,rain_mm,lote_id,operator,notes) VALUES(?,?,?,?,?)",
            (read_date, rain_mm, lote_id or None, operator, notes),
        )


def get_rain(start_date: Optional[str] = None, end_date: Optional[str] = None,
             lote_id: Optional[str] = None) -> list[dict]:
    sql = ("SELECT p.*, l.name AS lote_name FROM pluviometria p "
           "LEFT JOIN lotes l ON l.id=p.lote_id WHERE 1=1")
    args: list = []
    if start_date:
        sql += " AND p.read_date >= ?"; args.append(start_date)
    if end_date:
        sql += " AND p.read_date <= ?"; args.append(end_date)
    if lote_id:
        sql += " AND p.lote_id = ?"; args.append(lote_id)
    sql += " ORDER BY p.read_date DESC, p.id DESC"
    with _conn() as con:
        return [dict(r) for r in con.execute(sql, args).fetchall()]


def get_rain_total(start_date: Optional[str] = None,
                   end_date: Optional[str] = None) -> float:
    sql, args = "SELECT COALESCE(SUM(rain_mm),0) t FROM pluviometria WHERE 1=1", []
    if start_date:
        sql += " AND read_date >= ?"; args.append(start_date)
    if end_date:
        sql += " AND read_date <= ?"; args.append(end_date)
    with _conn() as con:
        row = con.execute(sql, args).fetchone()
    return round(float(row["t"] or 0), 1)

# ─── Protocolos Sanitários / Calendário de Vacinação ─────────────────────────

PROTOCOL_FREQUENCIES = {
    "unica":      "Dose única (uma vez na vida)",
    "anual":      "Anual",
    "semestral":  "Semestral",
    "trimestral": "Trimestral",
    "mensal":     "Mensal",
}
_FREQ_DAYS = {"anual": 365, "semestral": 182, "trimestral": 91, "mensal": 30}
SEX_TARGETS = {"ambos": "Machos e Fêmeas", "M": "Só Machos", "F": "Só Fêmeas"}












def _protocol_eligible(protocol: dict, animal: dict) -> bool:
    stt = protocol.get("sex_target", "ambos")
    if stt in ("M", "F") and animal["sex"] != stt:
        return False
    months = get_age_months(animal.get("birth_date"))
    if months is None:
        return False
    return (protocol.get("age_min") or 0) <= months <= (protocol.get("age_max") or 999)







# ─── Fotos dos Animais ───────────────────────────────────────────────────────

@_writes
def add_photo(animal_id: str, image_bytes: bytes, mime: str = "image/jpeg",
              taken_date: Optional[str] = None, operator: str = "") -> None:
    taken_date = taken_date or date.today().isoformat()
    with _conn() as con:
        _uuid_foto = uuid_de(con, animal_id)
        if _uuid_foto is None:
            raise ValueError(f"Animal {animal_id} não encontrado.")
        img = _conexao.psycopg2.Binary(image_bytes) if _conexao.USE_PG else image_bytes
        con.execute(
            "INSERT INTO animal_photos (animal_uuid,image,mime,taken_date,operator) VALUES(?,?,?,?,?)",
            (_uuid_foto, img, mime, taken_date, operator),
        )


def get_photos(animal_id: str) -> list[dict]:
    """Metadados das fotos (sem os bytes da imagem)."""
    with _conn() as con:
        rows = con.execute(
            "SELECT p.id,p.taken_date,p.operator,p.mime FROM animal_photos p "
            "JOIN animals a ON a.uuid=p.animal_uuid "
            "WHERE a.id=? ORDER BY p.taken_date DESC, p.id DESC",
            (animal_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_photo_image(photo_id: int):
    with _conn() as con:
        row = con.execute("SELECT image, mime FROM animal_photos WHERE id=?",
                          (photo_id,)).fetchone()
    if not row:
        return None
    return bytes(row["image"]), row["mime"]


def get_latest_photo(animal_id: str):
    with _conn() as con:
        row = con.execute(
            "SELECT p.image, p.mime FROM animal_photos p "
            "JOIN animals a ON a.uuid=p.animal_uuid WHERE a.id=? "
            "ORDER BY p.taken_date DESC, p.id DESC LIMIT 1", (animal_id,)
        ).fetchone()
    if not row:
        return None
    return bytes(row["image"]), row["mime"]


@_writes
def delete_photo(photo_id: int) -> None:
    with _conn() as con:
        con.execute("DELETE FROM animal_photos WHERE id=?", (photo_id,))
