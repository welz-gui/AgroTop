# AgroTop — Sistema de Gestão de Gado de Corte

O **AgroTop** é um sistema completo em formato PWA (Progressive Web App) focado no acompanhamento, gestão e análise de rebanhos de gado de corte. Desenvolvido para funcionar tanto no escritório quanto no campo, o sistema oferece controle total sobre produção, pesagem, custos, nutrição, estoque e parte sanitária de sua fazenda.

## 🚀 Funcionalidades Principais

- **📊 Dashboard:** Visão geral da fazenda com KPIs, evolução de peso do rebanho, gráficos por raça e distribuição de GMD (Ganho Médio Diário).
- **📱 Modo Campo:** Interface otimizada (mobile-first) para manejo rápido: pesagens, medicamentos, movimentação, fotos e registro de óbitos com menos cliques, projetada para funcionar com luvas e ao sol.
- **📋 Rebanho (Inventário e Fichas):** Consulta fácil a todo o rebanho, detalhamento por animal, histórico de peso com gráfico de tendência, histórico sanitário e financeiro individual.
- **🌿 Lotes / Pastagem:** Controle de lotação (UA/ha), capacidade de pasto, histórico de ocupação e visualização de todos os animais no piquete.
- **📈 Desempenho:** Metas de ganho de peso, simulações de terminação (pasto, semiconfinamento, confinamento), comparativo entre piquetes e projeção de abate.
- **💰 Financeiro & Mercado:** Previsão de lucro e breakeven, lançamento de vendas (por kg, lote ou cabeça), gestão de custos operacionais/fixos e análise de mortalidade e ranking de fornecedores.
- **📦 Estoque de Insumos:** Registro de medicamentos, vacinas e rações, com alertas visuais para níveis críticos e mínimo.
- **🌾 Nutrição:** Cadastro de planos de trato para os piquetes, confirmações de fornecimento de silo/sal, e descontos de estoque automáticos.
- **💉 Calendário Sanitário:** Controle e aplicação em lote de protocolos e esquemas vacinais (aftosa, brucelose, vermifugação).
- **🌧️ Clima & Chuva:** Previsão do tempo atualizada (via Open-Meteo) e pluviometria por piquete, com gráficos históricos da chuva.
- **🔔 Alertas Automáticos:** Notificações sobre animais sumidos (sem pesar há dias), períodos de carência em medicamentos, lotes de gado prontos para abate, falta de estoque e baixo GMD.
- **📄 Relatórios:** Geração rápida de CSV, planilhas em Excel e arquivos PDF de toda a sua operação (pesagens, inventário, etc.).

## 💻 Tecnologias Utilizadas

- **Framework Web:** [Streamlit](https://streamlit.io/)
- **Visualizações (Gráficos):** [Plotly](https://plotly.com/python/)
- **Processamento de Dados:** [Pandas](https://pandas.pydata.org/), Numpy
- **Banco de Dados:** SQLite (padrão local offline) / PostgreSQL (via Supabase na nuvem)
- **Geração de Documentos:** `openpyxl` (Excel), `fpdf2` (PDF)
- **Extra:** OCR e QR Code parsing com `Pillow`, `opencv-python-headless` e `pytesseract`.

## 🛠️ Como Executar o Projeto

1. Clone o repositório ou faça o download dos arquivos.
2. É recomendado criar um ambiente virtual em Python.
3. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```
4. Execute o aplicativo localmente:
   ```bash
   streamlit run app.py
   ```
   *Alternativa Windows:* Você também pode rodar através do arquivo `Iniciar_AgroTop.bat`.

O sistema vai inicializar um banco SQLite local (`agrotop.db`) e popular algumas tabelas iniciais se estiverem vazias, abrindo o navegador com a aplicação.

## 🔐 Credenciais Padrão (Seed Inicial)

O banco é criado com 2 usuários padrão na primeira inicialização, com senhas configuráveis via variáveis de ambiente.
*   **Administrador:**
    *   Usuário: `admin`
    *   Senha: Definida pela variável de ambiente `AGROTOP_ADMIN_PASSWORD`
*   **Operador de Campo:** (Não vê abas financeiras, apenas leitura e operação rápida)
    *   Usuário: `op1`
    *   Senha: Definida pela variável de ambiente `AGROTOP_OP_PASSWORD`

Se as variáveis de ambiente não estiverem definidas, senhas seguras e aleatórias serão geradas e exibidas no log (stdout) durante a inicialização.

## 🗄️ Banco de Dados

O AgroTop usa a seguinte lógica para o Banco de Dados:
- **Local (SQLite):** É o modo padrão caso não haja varíaveis de ambiente. Ideal para operação 100% offline. Todo o armazenamento é feito num arquivo único (`agrotop.db`).
- **Nuvem (PostgreSQL):** Caso você queira sincronizar múltiplos dispositivos ou instalar em um servidor remoto, basta fornecer a variável de ambiente `DATABASE_URL` contendo a sua string de conexão para uma instância do PostgreSQL (como Supabase, Railway ou RDS). O sistema traduz automaticamente as chamadas necessárias de SQL.
