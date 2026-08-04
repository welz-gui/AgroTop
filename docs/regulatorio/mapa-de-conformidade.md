# Mapa de Conformidade do AgroTop ao PNIB e Regulamentação RS

**Versão:** 1.0  
**Data de referência:** 04/08/2026  
**Documento base:** [`docs/regulatorio/requisitos_sistema_pnib_rs.md`](file:///d:/%C3%81rea%20de%20Trabalho/AgroTop-0032/docs/regulatorio/requisitos_sistema_pnib_rs.md)

---

## Resumo Executivo de Conformidade

- **`✅ atendido`**: 13
- **`🟡 parcial`**: 10
- **`❌ não atendido`**: 1
- **`⏳ fora de prazo`**: 1
- **`➖ não se aplica`**: 1
- **Total de Seções Mapeadas**: 26

---

## Tabela de Mapeamento Seção por Seção do PNIB

| § | Exigência | Situação | Onde / O que falta |
|---|---|---|---|
| §1 | Objetivo geral e escopo do sistema pecuário PNIB/RS | 🟡 parcial | Onde: `services/validacao_regulatoria.py` (`validar_animal`), `services/regras_regulatorias.py` (`avaliar`). Falta: finalização da integração oficial com a API da Seapi/RS e Base Central PNIB. |
| §2 | Contexto regulatório e prazos de implantação | ⏳ fora de prazo | Onde: `docs/regulatorio/requisitos_sistema_pnib_rs.md`. Exigência de obrigatoriedade total de trânsito individual entra em vigor somente em 01/01/2033 (§2). |
| §3 | Estrutura organizacional (Multi-organização e Propriedades) | ✅ atendido | Onde: `database.py` (`init_db`), `repositories/propriedades.py` (`get`), `services/geometria.py` (`area_hectares`), `app.py`. |
| §4 | Cadastro individual do animal e identificadores imutáveis | ✅ atendido | Onde: `database.py` (`init_db`), `repositories/animais.py` (`add_animal`), `repositories/identificadores.py` (`aplicar`), `services/identificadores.py` (`validar`), `services/estados_animal.py` (`transicao_permitida`). |
| §5 | Cadastro e controle de estoque de dispositivos de identificação | ✅ atendido | Onde: `database.py` (`init_db`), `repositories/dispositivos.py` (`aplicar`), `services/estados_dispositivo.py` (`transicao_permitida`), `services/dispositivos.py` (`validar_aplicacao`), `app.py`. |
| §6 | Histórico de eventos e imutabilidade auditável do animal | ✅ atendido | Onde: `database.py` (`init_db`), `repositories/movimentacoes.py` (`criar`), `repositories/nascimentos.py` (`registrar`), `repositories/pesagens.py` (`add_weighing`). |
| §7 | Nascimentos e vínculo materno | ✅ atendido | Onde: `database.py` (`init_db`), `repositories/nascimentos.py` (`registrar`), `services/genealogia.py` (`validar_vinculo`), `app.py`. |
| §8 | Movimentações, vendas, transferências e validação de GTA | ✅ atendido | Onde: `database.py` (`init_db`), `repositories/movimentacoes.py` (`criar`), `services/gta.py` (`validar`), `app.py`. |
| §9 | Manejo sanitário, vacinação e controle de carência | 🟡 parcial | Onde: `database.py` (`init_db`), `repositories/sanidade.py` (`add_medication`), `services/recomendacoes.py` (`avaliar`). Falta: interface em `app.py` para registro direto de vacinação contra brucelose (§9.2). |
| §10 | Integração com sistemas oficiais (Seapi/RS e PNIB) | 🟡 parcial | Onde: `database.py` (`init_db`), `repositories/movimentacoes.py` (`criar`), `services/gta.py` (`validar`). Falta: conectores HTTP/REST para homologação com endpoints externos da Seapi/RS quando disponibilizados. |
| §11 | Motor de regras regulatórias configurável | 🟡 parcial | Onde: `services/regras_regulatorias.py` (`avaliar`, `simular`). Falta: interface visual de gerenciamento e simulação de regras em `app.py`. |
| §12 | RFID, leitores e equipamentos de identificação eletrônica | 🟡 parcial | Onde: `services/dispositivos.py` (`expandir_faixa`, `validar_aplicacao`), `repositories/identificadores.py` (`aplicar`). Falta: integração via SDK/Bluetooth/Serial com bastões e balanças em `app.py`. |
| §13 | Aplicativo móvel e funcionamento offline | 🟡 parcial | Onde: `poc/mobile/` (módulo PoC Flutter + API FastAPI), `services/importacao.py` (`parse_pesagens`). Falta: sincronização bidirecional e tratamento offline de conflitos em produção. |
| §14 | Auditoria, integridade e permissões em ações sensíveis | ✅ atendido | Onde: `database.py` (`init_db`), `services/seguranca.py` (`_hash`, `_verify_password`), `services/estados_animal.py` (`transicao_permitida`). |
| §15 | Segurança, controle de acesso e LGPD | ✅ atendido | Onde: `database.py` (`init_db`), `services/seguranca.py` (`_hash`, `_verify_password`), `repositories/propriedades.py` (`get`). |
| §16 | Relatórios, fichas individuais e painel de conformidade | 🟡 parcial | Onde: `services/completude.py` (`avaliar_mes`), `app.py`. Falta: painel visual consolidado de indicadores de conformidade §-por-§. |
| §17 | Importação, migração e qualidade de dados | ✅ atendido | Onde: `services/importacao.py` (`parse_pesagens`), `services/qualidade.py` (`avaliar_pesagem`), `services/validacao_regulatoria.py` (`validar_animal`). |
| §18 | API do sistema (FastAPI / OpenAPI) | 🟡 parcial | Onde: `poc/mobile/` (módulo PoC Flutter + API FastAPI). Falta: publicação da documentação OpenAPI da API principal em produção. |
| §19 | Modelo de dados mínimo e DDL | ✅ atendido | Onde: `database.py` (`init_db`). |
| §20 | Requisitos não funcionais (Disponibilidade, backup, resiliência) | ✅ atendido | Onde: `tools/backup_banco.py` (`fazer_backup`), `tools/restaurar_banco.py` (`restaurar`), `database.py` (`init_db`). |
| §21 | Critérios de aceite de preparação do sistema | 🟡 parcial | Onde: `services/validacao_regulatoria.py` (`validar_animal`), `services/dispositivos.py` (`situacao_do_estoque`), `services/genealogia.py` (`validar_vinculo`). Falta: reconexão automática com retornos oficiais da Seapi/RS. |
| §22 | Priorização recomendada | ✅ atendido | Onde: `specs/QUADRO.md`, `ROADMAP.md`. |
| §23 | Pontos a confirmar oficialmente pela Seapi/RS | ➖ não se aplica | Onde: `docs/regulatorio/requisitos_sistema_pnib_rs.md`. Trata-se de definições de terceiros aguardando publicação por órgão oficial. |
| §24 | Checklist para o desenvolvedor | 🟡 parcial | Onde: `docs/regulatorio/requisitos_sistema_pnib_rs.md`. Falta: marcar checklist mobile/RFID completo quando módulos de hardware forem entregues. |
| §25 | Referências oficiais | ✅ atendido | Onde: `docs/regulatorio/requisitos_sistema_pnib_rs.md`. |
| §26 | Observação final e homologação | ❌ não atendido | Onde: N/A. O sistema ainda não passou por processo formal de homologação junto à Seapi/RS e MAPA. |

---

## Principais Lacunas Identificadas

1. **§10 - Integração com Sistemas Oficiais (Seapi/RS e PNIB):**
   * **Gravidade:** Alta.
   * **Situação:** `🟡 parcial`.
   * **Por quê:** O schema da Fase B e os validadores locais (`services/gta.py`, `services/validacao_regulatoria.py`) estão prontos, mas os conectores REST/HTTP de comunicação direta com os endpoints governamentais dependem da disponibilização das APIs públicas oficiais.

2. **§11 - Motor de Regras Regulatórias em Interface:**
   * **Gravidade:** Média.
   * **Situação:** `🟡 parcial`.
   * **Por quê:** O motor de regras puro (`services/regras_regulatorias.py`) suporta a criação e avaliação dinâmica de regras com níveis informativo/alerta/bloqueio, porém falta a tela administrativa em `app.py` para parametrização pelos gestores.

3. **§12 - Leitura Física e Integração com Equipamentos RFID:**
   * **Gravidade:** Média.
   * **Situação:** `🟡 parcial`.
   * **Por quê:** A lógica de estoque e verificação de brincos eletrônicos (`services/dispositivos.py`) foi implementada, contudo o suporte a pareamento Bluetooth/Serial com bastões e balanças de manejo no campo ainda não está integrado ao frontend Web.
