# Requisitos para adequação de sistema pecuário ao PNIB e à rastreabilidade individual no Rio Grande do Sul

**Versão:** 1.0  
**Data de referência:** 31/07/2026  
**Aplicação:** sistema de gestão de bovinos e bubalinos  
**Abrangência:** adequação progressiva ao PNIB, ao sistema estadual do Rio Grande do Sul e a protocolos complementares, como SISBOV e certificações privadas.

---

## 1. Objetivo

Preparar o sistema para:

1. identificar individualmente bovinos e bubalinos;
2. manter o histórico completo de cada animal;
3. registrar nascimentos, mortes, entradas, saídas, vendas, transferências e manejos sanitários;
4. operar com brincos visuais e identificadores eletrônicos;
5. integrar-se futuramente aos sistemas oficiais do Rio Grande do Sul e à Base Central de Dados do PNIB;
6. impedir ou alertar movimentações que não atendam às regras vigentes;
7. manter evidências e trilha de auditoria suficientes para fiscalização, certificação e conferência de estoque;
8. suportar várias propriedades sem precisar reestruturar o banco de dados no futuro.

> Este documento foi elaborado com base nas normas e informações disponíveis em 31/07/2026. Algumas especificações técnicas do PNIB e do modelo definitivo do Rio Grande do Sul ainda dependem de regulamentação, manuais e APIs oficiais. Por isso, regras, prazos, formatos e integrações devem ser configuráveis, e não fixados diretamente no código.

---

## 2. Contexto regulatório considerado

O sistema deve considerar os seguintes marcos:

- desenvolvimento da Base Central de Dados do PNIB;
- adequação dos sistemas estaduais até 31/12/2026;
- início progressivo da identificação entre 2027 e 2029 para animais enquadrados em manejos sanitários e protocolos privados definidos na regulamentação;
- ampliação da identificação entre 2030 e 2032;
- exigência de identificação individual antes da primeira movimentação ao final da implantação;
- vedação, a partir de 01/01/2033, da movimentação de bovinos ou bubalinos não identificados e não cadastrados conforme os padrões oficiais;
- possibilidade de o Rio Grande do Sul antecipar etapas ou criar exigências complementares;
- projeto-piloto da Seapi/RS com registro individual, dispositivos oficiais e comunicação de nascimentos, mortes, vendas e transferências.

### 2.1. Princípio de implementação

O sistema não deve assumir que:

- o brinco interno da fazenda equivale ao identificador oficial;
- RFID será obrigatório para todos os animais em todas as situações;
- o formato atual do piloto gaúcho será necessariamente o formato definitivo;
- a API estadual terá o mesmo formato da Base Central do PNIB;
- as regras serão iguais para todas as categorias de animais e propriedades.

Todas essas definições devem ser tratadas por configuração e versionamento.

---

## 3. Estrutura organizacional

O banco de dados deve ser estruturado para múltiplas organizações e múltiplas propriedades, mesmo que inicialmente exista apenas uma fazenda.

### 3.1. Hierarquia recomendada

```text
Organização
└── Produtor ou titular
    ├── Propriedade/estabelecimento A
    ├── Propriedade/estabelecimento B
    └── Propriedade/estabelecimento C
```

### 3.2. Dados da organização

- identificador interno;
- razão social ou nome;
- CPF ou CNPJ;
- contatos;
- responsável legal;
- status;
- data de criação;
- configurações de segurança e integração.

### 3.3. Dados do produtor ou titular

- identificador interno;
- CPF ou CNPJ;
- nome;
- inscrição ou cadastro estadual, quando aplicável;
- credenciais ou identificadores usados nos sistemas oficiais;
- contatos;
- procurações e responsáveis autorizados.

### 3.4. Dados da propriedade

- identificador interno imutável;
- nome da propriedade;
- código oficial do estabelecimento, quando existente;
- titular;
- município e UF;
- endereço;
- coordenadas e polígono geográfico, quando disponíveis;
- atividade predominante;
- espécies exploradas;
- situação cadastral;
- data de início e encerramento;
- vínculo com unidades produtivas, retiros, campos, piquetes ou instalações.

---

## 4. Cadastro individual do animal

Cada animal deve possuir um registro único e permanente.

### 4.1. Identificadores

O sistema deve armazenar separadamente:

- `animal_id`: identificador interno imutável, preferencialmente UUID;
- número interno de manejo;
- código oficial PNIB, quando atribuído;
- número visual do brinco oficial;
- código eletrônico RFID/EID;
- código SISBOV, quando aplicável;
- códigos de protocolos privados;
- identificadores anteriores;
- identificadores substituídos ou inutilizados.

### 4.2. Regras dos identificadores

1. Um código oficial não pode ser vinculado simultaneamente a dois animais ativos.
2. Um RFID não pode estar ativo em dois animais.
3. A substituição de brinco não deve apagar o identificador anterior.
4. A perda de brinco deve gerar um evento próprio.
5. A correção de identificação deve exigir justificativa e autorização.
6. O sistema deve impedir a reutilização indevida de identificadores.
7. O formato e a quantidade de dígitos do código oficial devem ser configuráveis.
8. Deve ser possível validar prefixos, dígitos verificadores e padrões definidos futuramente.
9. O número interno da fazenda deve continuar disponível mesmo após o cadastramento oficial.
10. O histórico de todos os dispositivos deve permanecer acessível.

### 4.3. Dados básicos do animal

- espécie;
- sexo;
- raça ou composição racial;
- pelagem;
- data de nascimento;
- tipo da data de nascimento: exata ou estimada;
- propriedade de nascimento;
- propriedade atual;
- categoria atual;
- situação atual;
- mãe;
- pai, quando conhecido;
- origem: nascido na propriedade, comprado, transferido ou importado;
- peso ao nascer, quando informado;
- fotos;
- características naturais ou biométricas;
- observações;
- data de inclusão;
- usuário responsável pelo cadastro.

### 4.4. Estados possíveis do animal

Exemplos:

- rascunho;
- ativo;
- ativo sem identificação oficial;
- identificado oficialmente;
- identificação pendente de sincronização;
- identificação rejeitada pelo sistema oficial;
- movimentação programada;
- em trânsito;
- vendido;
- transferido;
- abatido;
- morto;
- desaparecido;
- furtado;
- baixado por ajuste autorizado;
- cadastro bloqueado;
- cadastro duplicado em análise.

Os estados devem possuir regras de transição. Um animal morto ou abatido, por exemplo, não pode retornar ao estado ativo sem procedimento administrativo autorizado e auditado.

---

## 5. Cadastro e controle dos dispositivos de identificação

O sistema deve possuir um módulo de estoque de brincos e dispositivos.

### 5.1. Dados do dispositivo

- identificador interno;
- código visual;
- código eletrônico;
- tipo: brinco visual, boton, conjunto visual + eletrônico ou outro;
- tecnologia;
- fabricante;
- fornecedor;
- modelo;
- lote;
- data de fabricação;
- data de aquisição;
- proprietário do estoque;
- propriedade de destino;
- padrão técnico;
- status;
- data de aplicação;
- animal vinculado;
- aplicador;
- motivo de inutilização;
- data de devolução ou descarte.

### 5.2. Estados do dispositivo

- solicitado;
- recebido;
- disponível;
- reservado;
- aplicado;
- perdido;
- danificado;
- substituído;
- inutilizado;
- devolvido;
- cancelado;
- bloqueado pelo órgão oficial.

### 5.3. Requisitos operacionais

- importação de lotes por arquivo;
- leitura por código de barras, QR Code ou RFID;
- conferência entre número visual e eletrônico;
- alerta de divergência;
- aplicação individual e em lote;
- emissão de termo ou relatório de aplicação;
- inventário dos dispositivos;
- rastreamento de quem recebeu, transportou e aplicou cada dispositivo.

---

## 6. Histórico de eventos do animal

A rastreabilidade deve ser baseada em eventos.

### 6.1. Eventos mínimos

- nascimento;
- cadastro inicial;
- identificação interna;
- identificação oficial;
- aplicação de dispositivo;
- leitura e conferência;
- perda de brinco;
- dano ao dispositivo;
- substituição;
- retirada autorizada;
- entrada na propriedade;
- saída da propriedade;
- venda;
- compra;
- transferência sem mudança de titularidade;
- mudança de titularidade;
- emissão de GTA;
- cancelamento de GTA;
- chegada confirmada;
- recusa ou divergência na recepção;
- manejo sanitário;
- vacinação;
- vacinação contra brucelose;
- teste sanitário;
- tratamento;
- pesagem;
- mudança de lote;
- mudança de categoria;
- reprodução;
- aborto;
- parto;
- morte;
- abate;
- desaparecimento;
- furto ou abigeato;
- ajuste de inventário;
- bloqueio sanitário;
- desbloqueio;
- correção cadastral;
- sincronização com sistema oficial;
- rejeição pelo sistema oficial.

### 6.2. Dados comuns a todos os eventos

- identificador do evento;
- animal;
- tipo;
- data e hora em que ocorreu;
- data e hora em que foi registrado;
- propriedade;
- local interno;
- responsável pela execução;
- usuário que registrou;
- origem da informação;
- coordenadas, quando disponíveis;
- observações;
- anexos;
- fotos;
- documento relacionado;
- status da sincronização;
- identificador retornado pelo sistema oficial;
- versão do registro;
- registro anterior relacionado;
- justificativa de alteração ou cancelamento.

### 6.3. Imutabilidade

Eventos confirmados não devem ser apagados ou sobrescritos.

Quando houver erro:

1. manter o evento original;
2. gerar evento de correção, cancelamento ou estorno;
3. registrar usuário, data, motivo e autorização;
4. recalcular o estado atual do animal;
5. sincronizar a correção com os sistemas externos, quando aplicável.

---

## 7. Nascimentos e vínculo materno

### 7.1. Cadastro de nascimento

O fluxo deve permitir:

- selecionar ou ler a identificação da mãe;
- informar data e hora;
- registrar sexo;
- raça ou composição racial;
- peso;
- condição do nascimento;
- tipo de parto;
- identificar nascimento simples ou múltiplo;
- tirar fotos;
- gerar número interno;
- reservar ou aplicar dispositivo;
- indicar data estimada quando o nascimento não for acompanhado;
- registrar o responsável.

### 7.2. Validações

- a mãe deve ser fêmea e estar ativa na data do parto;
- a propriedade da mãe deve ser compatível com o local do nascimento;
- a data não pode ser posterior à data atual;
- gêmeos devem gerar animais distintos ligados ao mesmo parto;
- alterações no vínculo materno devem ser auditadas;
- o sistema deve detectar datas ou intervalos biologicamente inconsistentes e emitir alerta, sem substituir a avaliação técnica.

### 7.3. Pendências

O sistema deve gerar listas de:

- nascimentos sem identificação;
- animais sem mãe vinculada;
- animais com nascimento estimado;
- crias sem sexo, raça ou propriedade de nascimento;
- identificações aplicadas e ainda não comunicadas.

---

## 8. Movimentações, vendas e transferências

### 8.1. Tipos de movimentação

- entre propriedades do mesmo titular;
- entre propriedades de titulares diferentes;
- venda;
- compra;
- remate;
- empréstimo;
- parceria;
- exposição;
- evento agropecuário;
- retorno;
- envio ao frigorífico;
- transferência para confinamento;
- movimentação temporária;
- movimentação sanitária;
- outra prevista na regulamentação.

### 8.2. Dados mínimos

- origem;
- destino;
- titular de origem;
- titular de destino;
- finalidade;
- data prevista;
- data efetiva;
- transportador;
- veículo;
- animais;
- GTA;
- nota fiscal ou documento comercial;
- protocolo oficial;
- status;
- confirmação de chegada;
- divergências;
- anexos.

### 8.3. Pré-validação de saída

Antes de liberar uma movimentação, o sistema deve verificar:

- identificação exigida para o animal;
- cadastro oficial;
- propriedade atual;
- titularidade;
- status sanitário;
- bloqueios;
- exigências da finalidade;
- exigências do destino;
- documentos;
- GTA;
- consistência da quantidade;
- existência de sincronizações pendentes;
- duplicidade do animal em outra movimentação;
- regras estaduais e nacionais vigentes na data.

### 8.4. Bloqueios e alertas

As regras devem possuir três níveis:

- **informativo:** permite continuar;
- **alerta:** exige confirmação e justificativa;
- **bloqueio:** impede a operação sem autorização ou regularização.

Exemplos de bloqueio:

- animal morto ou abatido;
- dispositivo oficial duplicado;
- animal pertencente a outra propriedade;
- impedimento sanitário;
- movimentação já concluída;
- ausência de identificação quando ela for obrigatória;
- inconsistência que impeça emissão ou validação da GTA.

---

## 9. Manejo sanitário

### 9.1. Registros mínimos

- vacinação;
- vacina contra brucelose;
- testes de brucelose e tuberculose;
- coleta de amostras;
- tratamentos;
- medicamentos;
- carência;
- diagnóstico;
- quarentena;
- interdição;
- liberação;
- responsável técnico;
- lote do produto;
- validade;
- dose;
- via de aplicação;
- documento comprobatório.

### 9.2. Vacinação contra brucelose

Como a etapa inicial do PNIB envolve animais enquadrados no manejo sanitário previsto na regulamentação, o sistema deve:

- identificar quais animais estão sujeitos ao manejo;
- vincular a vacinação ao animal individual;
- registrar identificação utilizada no momento;
- armazenar médico-veterinário e documentação;
- controlar idade e elegibilidade;
- impedir duplicidade indevida;
- gerar lista de animais pendentes;
- gerar arquivo ou integração para o sistema oficial;
- manter evidência da comunicação e da aceitação.

As regras de idade, sexo, vacina, prazos e documentação devem ser parametrizáveis.

---

## 10. Integração com sistemas oficiais

### 10.1. Sistemas previstos

A arquitetura deve permitir integração com:

- sistema estadual da Seapi/RS;
- SDA/Produtor Online do Rio Grande do Sul;
- Base Central de Dados do PNIB;
- serviços de GTA;
- SISBOV;
- protocolos privados homologados;
- frigoríficos, leilões, laboratórios e certificadoras, quando autorizado.

### 10.2. Camada de integração

Não integrar regras externas diretamente ao núcleo do sistema.

Criar uma camada própria com:

- conectores por sistema;
- mapeamento de campos;
- autenticação;
- certificados digitais, quando exigidos;
- filas de envio;
- recebimento de retornos;
- tentativas automáticas;
- controle de indisponibilidade;
- idempotência;
- reconciliação;
- logs técnicos;
- versionamento de layouts;
- ambiente de homologação e produção;
- armazenamento dos protocolos oficiais.

### 10.3. Situação de sincronização

Cada cadastro ou evento integrável deve possuir:

- não aplicável;
- aguardando envio;
- em fila;
- enviado;
- processando;
- aceito;
- aceito com ressalva;
- rejeitado;
- erro técnico;
- aguardando correção;
- cancelamento solicitado;
- cancelado;
- divergente;
- reconciliado manualmente.

### 10.4. Funcionamento sem API oficial

Enquanto não houver API disponível, o sistema deve permitir:

- geração de arquivos em formato configurável;
- exportação CSV, XLSX, JSON e PDF;
- importação de retornos;
- registro manual de protocolo;
- anexação de comprovantes;
- checklist de lançamento no portal oficial;
- dupla conferência;
- marcação como comunicado externamente;
- posterior reconciliação com a integração automática.

---

## 11. Motor de regras regulatórias

As regras não devem ficar fixadas no código-fonte.

### 11.1. Estrutura das regras

Cada regra deve possuir:

- nome;
- descrição;
- fundamento;
- esfera: federal, estadual, protocolo ou interna;
- UF;
- espécie;
- categoria;
- sexo;
- faixa etária;
- finalidade;
- evento de aplicação;
- data inicial;
- data final;
- nível: informativo, alerta ou bloqueio;
- condição;
- mensagem ao usuário;
- exceções;
- documentação exigida;
- versão;
- responsável pela aprovação;
- data da última revisão.

### 11.2. Exemplos de regras configuráveis

- identificação obrigatória antes da primeira movimentação;
- identificação ligada a determinado manejo sanitário;
- dispositivo aceito;
- necessidade de cadastro oficial;
- prazo de comunicação;
- regras para substituição;
- documentos exigidos;
- bloqueios sanitários;
- regras específicas do Rio Grande do Sul;
- exigências de frigorífico ou protocolo privado.

### 11.3. Simulação regulatória

O administrador deve conseguir testar uma regra antes de ativá-la e verificar:

- animais afetados;
- movimentações que seriam bloqueadas;
- pendências geradas;
- impacto por propriedade;
- inconsistências nos dados atuais.

---

## 12. RFID e equipamentos

### 12.1. Leitura eletrônica

O sistema deve aceitar:

- leitores Bluetooth;
- leitores USB;
- leitores seriais;
- leitores integrados a balanças;
- leitura manual do código;
- importação de arquivo;
- integração por API ou SDK.

### 12.2. Requisitos da leitura

- associar leitura ao animal;
- mostrar número visual e eletrônico;
- alertar quando houver divergência;
- impedir duplicidade;
- registrar leitor, operador, data, hora e local;
- funcionar em lote;
- permitir leitura contínua;
- evitar registros duplicados por leitura repetida;
- armazenar leituras não reconhecidas para conferência;
- operar offline;
- sincronizar posteriormente.

### 12.3. Compatibilidade

O sistema deve ser preparado para os padrões técnicos que vierem a ser definidos oficialmente. A compatibilidade com RFID animal baseado nas normas ISO 11784/11785 deve ser considerada, mas não deve impedir a inclusão de outros padrões homologados no futuro.

---

## 13. Aplicativo móvel e funcionamento offline

O aplicativo de campo deve ser tratado como parte central da solução.

### 13.1. Funções offline

- consultar animais previamente sincronizados;
- cadastrar nascimento;
- aplicar identificador;
- ler RFID;
- registrar perda ou substituição;
- registrar manejo sanitário;
- registrar pesagem;
- movimentar entre lotes;
- tirar fotos;
- coletar assinatura;
- registrar coordenadas;
- montar movimentação;
- armazenar eventos até recuperar conexão.

### 13.2. Sincronização

- fila local criptografada;
- identificação única de cada operação;
- prevenção de duplicidade;
- resolução de conflitos;
- aviso de dados desatualizados;
- confirmação de envio;
- opção de reprocessamento;
- proibição de apagar operação ainda não sincronizada;
- registro do dispositivo utilizado.

### 13.3. Conflitos

Quando duas pessoas alterarem o mesmo animal offline, o sistema deve:

1. preservar as duas operações;
2. identificar o conflito;
3. aplicar automaticamente somente alterações compatíveis;
4. encaminhar conflitos críticos para revisão;
5. registrar a decisão tomada.

---

## 14. Auditoria e integridade

### 14.1. Trilha de auditoria

Registrar:

- usuário;
- data e hora;
- dispositivo;
- endereço IP, quando disponível;
- ação;
- registro anterior;
- registro posterior;
- motivo;
- autorização;
- origem: web, aplicativo, integração ou importação;
- protocolo externo.

### 14.2. Ações sensíveis

Devem exigir permissão específica:

- alterar identificador oficial;
- corrigir mãe;
- alterar data de nascimento;
- estornar morte ou abate;
- alterar propriedade de origem;
- cancelar movimentação concluída;
- excluir rascunhos;
- efetuar ajuste de inventário;
- reconciliar divergência oficial;
- alterar regra regulatória;
- conceder acesso administrativo.

### 14.3. Evidências

O sistema deve manter:

- anexos;
- fotos;
- documentos;
- protocolos;
- relatórios assinados;
- comprovantes de sincronização;
- hash ou mecanismo de verificação de integridade para documentos críticos.

---

## 15. Segurança e LGPD

### 15.1. Controle de acesso

Perfis mínimos:

- proprietário;
- administrador da organização;
- gerente da propriedade;
- responsável técnico;
- operador de manejo;
- operador de identificação;
- operador de movimentação;
- contador ou administrativo;
- auditor;
- consulta;
- suporte técnico.

### 15.2. Requisitos

- autenticação segura;
- autenticação em dois fatores para perfis sensíveis;
- permissões por organização e propriedade;
- menor privilégio;
- encerramento de sessões;
- logs de acesso;
- criptografia em trânsito;
- criptografia de dados sensíveis;
- backup;
- restauração testada;
- política de retenção;
- gestão de incidentes;
- segregação entre clientes;
- impossibilidade de um cliente consultar dados de outro.

### 15.3. Dados pessoais

O sistema deve:

- coletar somente os dados pessoais necessários;
- informar finalidade;
- controlar acesso;
- registrar compartilhamentos;
- permitir correção;
- definir retenção;
- atender solicitações aplicáveis da LGPD;
- preservar dados cuja manutenção seja necessária por obrigação legal ou regulatória.

---

## 16. Relatórios e consultas

### 16.1. Ficha individual

Deve apresentar:

- todos os identificadores;
- foto;
- dados básicos;
- genealogia;
- propriedade atual;
- histórico de propriedades;
- eventos;
- manejos sanitários;
- movimentações;
- dispositivos;
- documentos;
- situação regulatória;
- pendências;
- sincronizações.

### 16.2. Relatórios mínimos

- animais ativos;
- animais não identificados;
- animais sem identificação oficial;
- identificação pendente de envio;
- identificações rejeitadas;
- dispositivos disponíveis;
- dispositivos perdidos;
- substituições;
- inconsistência entre visual e RFID;
- nascimentos por período;
- mortes;
- entradas e saídas;
- saldo por propriedade;
- saldo por categoria;
- divergência entre estoque físico e sistema;
- animais sujeitos a manejo sanitário;
- vacinação pendente;
- animais bloqueados;
- movimentações pendentes;
- histórico de GTA;
- eventos não sincronizados;
- auditoria;
- rastreabilidade completa de origem a destino.

### 16.3. Painel de conformidade

Indicadores recomendados:

- percentual do rebanho identificado internamente;
- percentual com identificação oficial;
- percentual com RFID;
- animais sem origem completa;
- animais sem mãe;
- animais com inconsistência;
- eventos aguardando comunicação;
- rejeições oficiais;
- movimentações bloqueadas;
- dispositivos perdidos;
- diferença entre saldo cadastral e inventário;
- conformidade por propriedade.

---

## 17. Importação, migração e qualidade de dados

### 17.1. Importação

Permitir importação de:

- animais;
- brincos;
- RFID;
- propriedades;
- lotes;
- eventos;
- vacinações;
- pesagens;
- movimentações;
- documentos.

### 17.2. Processo de importação

1. enviar arquivo;
2. mapear colunas;
3. validar;
4. mostrar erros;
5. detectar duplicidades;
6. simular resultado;
7. confirmar;
8. gerar relatório;
9. permitir desfazer somente por procedimento auditado;
10. manter o arquivo original.

### 17.3. Validações de qualidade

- identificadores duplicados;
- animais em duas propriedades;
- eventos fora de ordem;
- morte anterior a nascimento;
- movimentação após morte;
- mãe mais nova que a cria;
- sexo incompatível com parto;
- datas futuras;
- dispositivo aplicado em mais de um animal;
- GTA repetida;
- propriedade inexistente;
- falta de origem;
- divergência de saldo.

---

## 18. API do sistema

O sistema deve disponibilizar API própria documentada para aplicativo, integrações e parceiros autorizados.

### 18.1. Características

- autenticação robusta;
- autorização por escopo;
- versionamento;
- paginação;
- filtros;
- idempotência;
- limites de requisição;
- logs;
- webhooks, quando aplicável;
- documentação OpenAPI;
- ambiente de testes;
- chaves separadas por integração.

### 18.2. Entidades mínimas

- organizações;
- produtores;
- propriedades;
- animais;
- identificadores;
- dispositivos;
- eventos;
- manejos sanitários;
- movimentações;
- documentos;
- sincronizações;
- regras;
- auditoria.

---

## 19. Modelo de dados mínimo

### 19.1. Tabelas ou entidades principais

```text
organizations
users
roles
user_property_permissions
owners
properties
property_official_registrations
animals
animal_identifiers
animal_identifier_history
animal_parentage
animal_events
event_attachments
devices
device_batches
device_assignments
herds_or_lots
animal_lot_history
sanitary_events
vaccinations
laboratory_tests
movements
movement_animals
movement_documents
gta_records
official_integrations
integration_messages
integration_attempts
integration_reconciliations
compliance_rules
compliance_results
audit_logs
notifications
imports
import_errors
```

### 19.2. Princípios do banco

- chaves internas imutáveis;
- isolamento por organização;
- histórico temporal;
- exclusão lógica somente onde for permitida;
- eventos confirmados imutáveis;
- restrições de unicidade;
- integridade referencial;
- datas armazenadas com fuso;
- suporte a anexos;
- campos externos extensíveis;
- armazenamento dos dados brutos recebidos e enviados nas integrações.

---

## 20. Requisitos não funcionais

### 20.1. Disponibilidade e desempenho

- consultas comuns com resposta rápida;
- leitura de RFID em lote sem travamento;
- filas para operações pesadas;
- sistema utilizável com internet rural limitada;
- sincronização resiliente;
- monitoramento de falhas;
- capacidade de crescimento para várias fazendas e clientes.

### 20.2. Backup

- backup automático;
- cópias em local separado;
- retenção configurada;
- criptografia;
- testes periódicos de restauração;
- registro dos testes;
- plano de continuidade.

### 20.3. Observabilidade

- logs estruturados;
- métricas;
- alertas;
- monitoramento das integrações;
- painel de filas;
- rastreamento de erros;
- histórico de indisponibilidade externa.

---

## 21. Critérios de aceite

O módulo será considerado preparado quando, no mínimo:

1. cada animal possuir identificador interno imutável;
2. for possível manter identificador interno, oficial, visual e eletrônico separadamente;
3. o sistema impedir duplicidade de identificador;
4. perdas e substituições preservarem o histórico;
5. nascimentos, mortes, vendas e transferências gerarem eventos auditáveis;
6. o animal possuir histórico de propriedades;
7. movimentações passarem por validação configurável;
8. regras não estiverem fixadas no código;
9. existir fila de integração com tentativas e protocolos;
10. a operação básica funcionar offline;
11. for possível importar e exportar dados;
12. todos os eventos críticos possuírem trilha de auditoria;
13. houver segregação entre organizações e propriedades;
14. existir relatório de animais não identificados e não sincronizados;
15. existir reconciliação entre sistema interno e retorno oficial;
16. nenhuma correção crítica apagar o dado anterior;
17. o sistema suportar novos tipos de identificador sem migração estrutural ampla;
18. a estrutura estiver apta a receber as especificações finais do PNIB e da Seapi/RS.

---

## 22. Priorização recomendada

### Prioridade 1 — Base obrigatória

- estrutura multi-organização e multi-propriedade;
- cadastro individual;
- identificadores separados;
- eventos;
- nascimentos;
- mortes;
- movimentações;
- dispositivos;
- auditoria;
- importação;
- relatórios de pendências.

### Prioridade 2 — Operação de campo

- aplicativo móvel;
- offline;
- RFID;
- aplicação em lote;
- manejos sanitários;
- fotos e documentos;
- conferência física.

### Prioridade 3 — Conformidade

- motor de regras;
- bloqueios;
- painel de conformidade;
- reconciliação;
- relatórios regulatórios;
- controle de protocolos.

### Prioridade 4 — Integrações oficiais

- conectores da Seapi/RS;
- GTA;
- Base Central do PNIB;
- SISBOV;
- protocolos privados;
- frigoríficos e parceiros.

A camada de integração deve ser criada desde o início, mesmo que os conectores oficiais sejam implementados somente quando as especificações estiverem disponíveis.

---

## 23. Pontos que ainda precisam ser confirmados oficialmente

Antes de considerar o sistema integralmente homologado, confirmar:

- formato definitivo do identificador oficial;
- tipos de dispositivos aceitos;
- obrigatoriedade ou não de RFID por categoria;
- fornecedores e dispositivos homologados;
- regras definitivas para distribuição;
- prazo de aplicação em animais nascidos;
- prazo de comunicação;
- procedimento de substituição;
- tratamento de animais identificados antes da implantação;
- integração com GTA;
- layout ou API da Seapi/RS;
- autenticação;
- dados obrigatórios;
- regras para animais vindos de outros estados;
- regras para eventos temporários;
- responsabilidades de produtores, veterinários, certificadoras e órgãos oficiais;
- penalidades;
- política de correção de dados;
- regras de acesso à Base Central;
- necessidade de homologação dos softwares privados.

---

## 24. Checklist para o desenvolvedor

### Arquitetura

- [ ] Multi-organização
- [ ] Multi-propriedade
- [ ] API versionada
- [ ] Aplicativo offline
- [ ] Camada de integração
- [ ] Fila de mensagens
- [ ] Motor de regras configurável
- [ ] Auditoria imutável

### Animais

- [ ] ID interno imutável
- [ ] Número de manejo
- [ ] Código oficial
- [ ] Brinco visual
- [ ] RFID
- [ ] Histórico de identificadores
- [ ] Mãe e pai
- [ ] Histórico de propriedades
- [ ] Estado atual calculado pelos eventos

### Dispositivos

- [ ] Estoque
- [ ] Lotes
- [ ] Aplicação
- [ ] Conferência visual/RFID
- [ ] Perda
- [ ] Substituição
- [ ] Inutilização
- [ ] Auditoria

### Eventos

- [ ] Nascimento
- [ ] Identificação
- [ ] Entrada
- [ ] Saída
- [ ] Venda
- [ ] Transferência
- [ ] Manejo sanitário
- [ ] Morte
- [ ] Abate
- [ ] Correção/estorno

### Regulação

- [ ] Regras por vigência
- [ ] Regras por UF
- [ ] Alertas e bloqueios
- [ ] Simulação
- [ ] Pendências
- [ ] Protocolos oficiais
- [ ] Reconciliação

### Segurança

- [ ] Perfis e permissões
- [ ] Segregação de clientes
- [ ] Criptografia
- [ ] Backup
- [ ] Restauração
- [ ] Logs
- [ ] LGPD

---

## 25. Referências oficiais

1. Ministério da Agricultura e Pecuária — PNIB:  
   https://www.gov.br/agricultura/pt-br/assuntos/sanidade-animal-e-vegetal/saude-animal/rastreabilidade-animal/pnib

2. Portaria SDA/MAPA nº 1.331, de 21 de julho de 2025 — cronograma de implementação:  
   https://www.in.gov.br/en/web/dou/-/portaria-sda/mapa-n-1.331-de-21-de-julho-de-2025-643581903

3. Secretaria da Agricultura do Rio Grande do Sul — Projeto Piloto de Rastreabilidade Individual de Bovinos e Bubalinos:  
   https://www.agricultura.rs.gov.br/rastreabilidade-bovina

4. Secretaria da Agricultura do Rio Grande do Sul — Declaração Anual de Rebanho e SDA/Produtor Online:  
   https://www.agricultura.rs.gov.br/declaracao

---

## 26. Observação final

Este documento deve ser usado como especificação de preparação e arquitetura, e não como declaração de que o sistema já está homologado pelo PNIB ou pela Seapi/RS.

A homologação ou conformidade definitiva dependerá da publicação dos manuais técnicos, layouts, APIs, regras estaduais e procedimentos operacionais oficiais. O sistema deve ser revisado sempre que houver nova regulamentação.
