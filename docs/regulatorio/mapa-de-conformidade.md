# Mapa de conformidade do AgroTop ao PNIB e à regulamentação RS

**Versão:** 2.0  
**Data de referência:** 05/08/2026  
**Documento base:** [`docs/regulatorio/requisitos_sistema_pnib_rs.md`](requisitos_sistema_pnib_rs.md)

## Resumo executivo

- **`✅ atendido`**: 10
- **`🟡 parcial`**: 11
- **`❌ não atendido`**: 1
- **`⏳ fora de prazo`**: 1
- **`➖ não se aplica`**: 3
- **Total de seções mapeadas**: 26

“Atendido” significa que há evidência no código para o escopo descrito; não é
certificação por órgão público. Lacunas permanecem registradas como parciais ou
não atendidas.

## Tabela seção por seção

| § | Exigência | Situação | Onde / o que falta |
|---|---|---|---|
| §1 | Objetivo geral e escopo do sistema pecuário PNIB/RS | 🟡 parcial | Onde: `services/validacao_regulatoria.py` (`validar_animal`), `services/regras_regulatorias.py` (`avaliar`). Falta: integração oficial com Seapi/RS e Base Central PNIB. |
| §2 | Contexto regulatório e prazos de implantação | ⏳ fora de prazo | A identificação oficial para trânsito será exigível a partir de 01/01/2033; o prazo deve permanecer parametrizável. |
| §3 | Estrutura organizacional e propriedades | ✅ atendido | Onde: `database.py` (`init_db`), `repositories/propriedades.py` (`get`), `services/geometria.py` (`area_hectares`), `app.py`. |
| §4 | Cadastro individual e identificadores imutáveis | ✅ atendido | Onde: `repositories/animais.py` (`add_animal`), `repositories/identificadores.py` (`aplicar`), `services/identificadores.py` (`validar`), `services/estados_animal.py` (`transicao_permitida`), `app.py`. |
| §5 | Cadastro e controle de dispositivos de identificação | ✅ atendido | Onde: `repositories/dispositivos.py` (`aplicar`), `services/estados_dispositivo.py` (`transicao_permitida`), `services/dispositivos.py` (`validar_aplicacao`), `app.py`. |
| §6 | Histórico de eventos e imutabilidade auditável do animal | 🟡 parcial | Os eventos são gravados por `repositories/eventos.py` (`registrar`) e pelos repositórios de nascimentos, movimentações e pesagens. Falta: interface em `app.py` para consultar a linha do tempo do animal. |
| §7 | Nascimentos e vínculo materno | ✅ atendido | Onde: `repositories/nascimentos.py` (`registrar`), `services/genealogia.py` (`validar_vinculo`), `app.py`. |
| §8 | Movimentações, vendas, transferências e GTA | ✅ atendido | Onde: `repositories/movimentacoes.py` (`criar`), `services/gta.py` (`validar`), `app.py`. |
| §9 | Manejo sanitário, vacinação e carência | 🟡 parcial | Onde: `repositories/sanidade.py` (`add_medication`), `services/recomendacoes.py` (`avaliar`). Falta: fluxo de vacinação contra brucelose com evidência individual e integração oficial em `app.py`. |
| §10 | Integração com sistemas oficiais | 🟡 parcial | Onde: `repositories/eventos.py` (`marcar_sincronizado`), `repositories/eventos.py` (`registrar`). Falta: conectores HTTP/REST homologados para Seapi/RS e PNIB. |
| §11 | Motor de regras regulatórias configurável | 🟡 parcial | Onde: `services/regras_regulatorias.py` (`avaliar`, `simular`). Falta: interface administrativa para editar e simular regras em `app.py`. |
| §12 | RFID, leitores e equipamentos | 🟡 parcial | Onde: `services/dispositivos.py` (`expandir_faixa`, `validar_aplicacao`). Falta: integração Bluetooth, USB, serial e offline com equipamentos de campo. |
| §13 | Aplicativo móvel e funcionamento offline | 🟡 parcial | Onde: `poc/mobile/` e `services/importacao.py` (`parse_pesagens`). Falta: sincronização bidirecional de produção e resolução de conflitos offline. |
| §14 | Auditoria, integridade e permissões em ações sensíveis | ✅ atendido | Onde: `database.py` (`init_db`), `services/seguranca.py` (`_hash`, `_verify_password`), `services/estados_animal.py` (`transicao_permitida`), `app.py`. |
| §15 | Segurança, controle de acesso e LGPD | ✅ atendido | Onde: `services/seguranca.py` (`_hash`, `_verify_password`), `repositories/propriedades.py` (`get`), `database.py` (`init_db`), `app.py`. |
| §16 | Relatórios, fichas individuais e painel de conformidade | 🟡 parcial | Onde: `services/completude.py` (`avaliar_mes`), `app.py`. Falta: painel consolidado de indicadores por seção do PNIB. |
| §17 | Importação, migração e qualidade de dados | ✅ atendido | Onde: `services/importacao.py` (`parse_pesagens`), `services/qualidade.py` (`avaliar_pesagem`), `services/validacao_regulatoria.py` (`validar_animal`), `app.py`. |
| §18 | API do sistema (FastAPI/OpenAPI) | 🟡 parcial | Onde: `poc/mobile/`. Falta: publicação e operação da documentação OpenAPI da API principal. |
| §19 | Modelo de dados mínimo e DDL | ✅ atendido | Onde: `database.py` (`init_db`). |
| §20 | Disponibilidade, backup e resiliência | ✅ atendido | Onde: `tools/backup_banco.py` (`fazer_backup`), `tools/restaurar_banco.py` (`restaurar`), `database.py` (`init_db`). |
| §21 | Critérios de aceite de preparação do sistema | 🟡 parcial | Onde: `services/validacao_regulatoria.py` (`validar_animal`), `services/dispositivos.py` (`situacao_do_estoque`), `services/genealogia.py` (`validar_vinculo`). Falta: reconciliação automática com retornos oficiais. |
| §22 | Priorização recomendada | ➖ não se aplica | É orientação de planejamento do documento de requisitos, não uma exigência funcional do sistema. A fila vigente está em `specs/QUADRO.md`. |
| §23 | Pontos a confirmar oficialmente pela Seapi/RS | ➖ não se aplica | São definições de terceiros aguardando publicação oficial; não há implementação a certificar. |
| §24 | Checklist para o desenvolvedor | 🟡 parcial | Onde: `docs/regulatorio/requisitos_sistema_pnib_rs.md`. Falta: concluir os itens de hardware móvel/RFID quando os módulos forem entregues. |
| §25 | Referências oficiais | ➖ não se aplica | A seção registra fontes normativas em `docs/regulatorio/requisitos_sistema_pnib_rs.md`; não é comportamento implementável. |
| §26 | Observação final e homologação | ❌ não atendido | O sistema ainda não passou por homologação formal junto à Seapi/RS e ao MAPA. |

## Três lacunas prioritárias

1. **§6 — linha do tempo do animal:** sem consulta na interface, o histórico
   append-only não é auditável pelo operador que precisa conferi-lo.
2. **§10 — integração oficial:** sem conectores homologados, os registros não
   chegam aos sistemas públicos nem recebem reconciliação automática.
3. **§11 — administração das regras:** sem tela de simulação, mudanças de regra
   não podem ser avaliadas pelos responsáveis antes de entrar em vigor.

## Limites do mapa

Este documento descreve o estado verificável do código em 05/08/2026. Não afirma
conformidade jurídica, homologação ou equivalência entre dados armazenados e
aceitação por um órgão oficial.
