# Mapa de conformidade do AgroTop ao PNIB e à regulamentação RS

**Versão:** 2.1  
**Data de referência:** 05/08/2026 (revisado após a #98, mesma data)  
**Documento base:** [`docs/regulatorio/requisitos_sistema_pnib_rs.md`](requisitos_sistema_pnib_rs.md)

## Resumo executivo

- **`✅ atendido`**: 12
- **`🟡 parcial`**: 9
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
| §6 | Histórico de eventos e imutabilidade auditável do animal | ✅ atendido | Onde: `repositories/eventos.py` (`registrar`, `corrigir`, `do_animal`), `app.py` (`_linha_do_tempo_do_animal`, `_cartao_de_evento`). A correção não sobrescreve — cria evento novo apontando para o original (§6.3). |
| §7 | Nascimentos e vínculo materno | ✅ atendido | Onde: `repositories/nascimentos.py` (`registrar`), `services/genealogia.py` (`validar_vinculo`), `app.py`. |
| §8 | Movimentações, vendas, transferências e GTA | ✅ atendido | Onde: `repositories/movimentacoes.py` (`criar`), `services/gta.py` (`validar`), `app.py`. |
| §9 | Manejo sanitário, vacinação e carência | 🟡 parcial | Onde: `repositories/sanidade.py` (`add_medication`), `services/recomendacoes.py` (`avaliar`). Falta: fluxo de vacinação contra brucelose com evidência individual e integração oficial em `app.py`. |
| §10 | Integração com sistemas oficiais | 🟡 parcial | Onde: `repositories/eventos.py` (`marcar_sincronizado`, `registrar_situacao`), `app.py` (`page_sincronizacao`, `_sinc_acompanhar`, `_sinc_fechar_em_lote`) — §10.3 e §10.4 (registro manual de protocolo, dupla conferência) atendidos. Falta: §10.1/§10.2, os conectores automáticos por sistema (Seapi/RS, Base Central PNIB, GTA, SISBOV) e a importação/exportação de arquivos de retorno. |
| §11 | Motor de regras regulatórias configurável | ✅ atendido | Onde: `services/regras_regulatorias.py` (`avaliar`, `simular`), `app.py` (`page_regras`). Não existe editar: só nova versão, com simulação de alcance antes de salvar. |
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

> Revisão de 05/08/2026: a versão anterior listava §6 e §11 aqui. As duas ganharam
> interface na mesma data (§6 pela PR #98; §11 já a tinha desde a PR #88, e a versão
> anterior deste mapa não conferiu `app.py` antes de marcar — o mesmo erro que fechou a
> tentativa anterior desta spec, só que em outra seção).

1. **§10 — integração automática:** o registro manual (§10.3/§10.4) tem tela; os
   conectores por sistema (§10.1/§10.2) não existem. Enquanto isso, cada comunicação
   ao órgão depende de alguém lançar no portal e marcar aqui — funciona, mas não
   escala além do tamanho de operação atual.
2. **§12 — RFID e equipamentos:** nenhuma linha de código fecha isto sozinha. Depende
   de leitor em mãos para integrar via Bluetooth/USB/serial — é hardware, não backlog.
3. **§26 — homologação formal:** o sistema nunca foi submetido à Seapi/RS nem ao MAPA.
   Todo ✅ deste mapa é "evidência no código", não certificação — é a distinção que a
   nota de rodapé do resumo executivo existe para não deixar escapar.

## Limites do mapa

Este documento descreve o estado verificável do código em 05/08/2026. Não afirma
conformidade jurídica, homologação ou equivalência entre dados armazenados e
aceitação por um órgão oficial.
