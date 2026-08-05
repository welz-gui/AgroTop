# AgroTop — Sistema de Gestão de Gado de Corte

Sistema em formato PWA para acompanhamento, gestão e análise de rebanhos de corte —
escritório e campo. Controla produção, pesagem, custos, nutrição, estoque e sanidade.

Desde julho de 2026 o projeto tem um segundo objetivo, que reordenou tudo: **conformidade
com o PNIB** (Programa Nacional de Identificação Individual de Bovinos e Bubalinos,
Portaria SDA/MAPA 1.331/2025). Isso muda a natureza do produto — de software de gestão para
sistema de rastreabilidade com valor regulatório. Ver
[ADR 0004](docs/adr/0004-conformidade-pnib.md).

**Última revisão desta página:** 2026-08-05.

---

## Estado real do projeto

| | |
|---|---|
| Produção | Streamlit Community Cloud, deploy a cada push na `main` |
| Banco | Supabase/PostgreSQL · **32 tabelas, 362 colunas** |
| Testes | **492**, verdes em SQLite **e** PostgreSQL no CI (~9 min: 6 provas de interface) |
| Código | `app.py` (~3.700) · `database.py` (~2.100, fachada) · `repositories/` (12) · `services/` (25) · `ui/` · `tools/` (6) |
| Migrations | 13, versionadas, com rollback documentado |
| Fase A | ✅ concluída — refatoração em camadas |
| Fase B | ✅ concluída — B1 a B7, fundação regulatória |
| Fase B na tela | ✅ 6 de 7 — falta a linha do tempo do animal (§6) |

### O que a Fase B fez, e o que ainda falta

A fundação regulatória está **em produção e testada**: identidade imutável separada do
brinco, eventos e auditoria append-only, genealogia, hierarquia de propriedades,
movimentação com GTA, estoque de dispositivos e motor de regras configurável.

**A interface foi ligada em 2026-08-04**, em seis telas: **nascimento** (§7),
**estoque de brincos** (§5), **movimentação com GTA** (§8), **pendências de
conformidade** (§7.3), **propriedades com perímetro** (§3) e **motor de regras** (§11).

Falta uma: a **linha do tempo do animal** (§6). Os eventos são gravados em toda operação
desde o B2 — só não há tela que os mostre.

Isso é conformidade de **arquitetura**, não de **uso**. É a maior pendência do projeto, e
está registrada como tal no [ROADMAP](ROADMAP.md).

---

## Funcionalidades em produção (visíveis ao usuário)

- **📊 Dashboard** — KPIs, evolução de peso, distribuição por raça e GMD.
- **📱 Modo Campo** — pesagem, medicamento, movimentação entre piquetes, foto, óbito e
  **importação de pesagens por CSV** do indicador de balança. Mobile-first, pensado para
  uso com luva e ao sol.
- **➕ Cadastrar** — duas abas, porque são dois fatos: **comprado** (fornecedor, preço) e
  **nascido na fazenda**, com vínculo materno, gêmeos no mesmo parto e a validação do §7.
  Bloqueio para o fluxo; alerta pede confirmação, sem substituir a avaliação técnica.
- **🏷️ Brincos** — estoque de dispositivos do §5: importação por faixa numérica,
  aplicação em animal com conferência visual × eletrônico, e as doze situações do §5.2.
  Situação definitiva não oferece saída; `bloqueado_orgao` diz quem libera.
- **🏞️ Propriedades** — hierarquia Organização → Produtor → Propriedade do §3, com o
  **perímetro em GeoJSON**: área, perímetro e centro são **calculados** do desenho, nunca
  digitados. O titular é definido na criação e só muda por transferência (§8).
- **📜 Regras** — motor do §11: regra é **dado**, com vigência e versão. Não existe
  editar — só nova versão, porque o que já foi julgado precisa continuar explicado pelo
  texto que valia então. A simulação mostra o alcance no rebanho **antes** de salvar.
- **🚚 Movimentação** — trânsito entre propriedades do §8, distinto do piquete→piquete
  do Modo Campo: rascunho, pré-validação da saída, liberação com justificativa escrita
  quando há alerta, e confirmação de chegada que registra quem não chegou.
- **📋 Rebanho** — inventário, ficha individual com curva de peso, histórico sanitário e
  financeiro, e **gestão de identificadores com histórico**: trocar brinco encerra o
  anterior sem apagá-lo (§4.2.3 do PNIB).
- **🌿 Lotes / Pastagem** — lotação UA/ha, capacidade, ocupação.
- **📈 Desempenho** — metas, simulação de terminação, projeção de abate.
- **💰 Financeiro** — venda por kg/lote/cabeça, custo médio ponderado, breakeven,
  mortalidade, ranking de fornecedor.
- **📦 Estoque · 🌾 Nutrição · 💉 Sanitário · 🌧️ Clima** — insumos com alerta de mínimo,
  planos de trato com baixa automática, protocolos vacinais, chuva e previsão.
- **🔔 Alertas** — duas abas, porque são duas perguntas: **operacionais** (animais
  sumidos, carência, prontos para abate, estoque baixo, e o **motor de recomendações**, que
  mostra o motivo e os números de cada sugestão) e **conformidade §7.3** — o que falta nos
  dados, com o prazo de cada exigência. Pendência que só vale a partir de 2033 aparece
  como ⏳ e **fica fora do contador**: número que nunca zera ninguém lê.
- **⚙️ Admin** — usuários, edição direta de dados, e **mudança de status com máquina de
  estados**: sair de um estado final exige autorização e justificativa, que vão para a
  trilha de auditoria.
- **📄 Relatórios** — CSV, Excel e PDF.

## Fundação regulatória

| Módulo | O que faz | §PNIB |
|---|---|---|
| `animal_events` | linha do tempo do animal, **append-only por gatilho** | §6 |
| `audit_logs` | quem mudou o quê, quando, com que autorização | §14 |
| `evento_sincronizacao` | o que já foi comunicado ao sistema oficial, **também append-only** | §10 |
| `properties` | Organização → Produtor → Propriedade | §3 |
| `movimentacoes` | trânsito entre propriedades, GTA, divergência de recepção | §8 |
| `dispositivos` | estoque de brincos, 12 estados, conferência visual×eletrônico | §5 |
| `regras_regulatorias` | regras como **dado**, com vigência e versionamento | §11 |

---

## Arquitetura

```
app.py           interface Streamlit (ainda monolítica)
database.py      FACHADA — reexporta; não adicione consulta nova aqui
repositories/    SQL, e só SQL. Um módulo por agregado
services/        regra de negócio pura — sem banco, sem Streamlit
ui/tema.py       tokens de cor semânticos (escuro e claro)
tools/           backup, restauração, dump de schema, auditoria de cores
```

Duas regras sustentam isso, detalhadas no [ROADMAP](ROADMAP.md):

- **`_conn()` é o único ponto de acesso ao banco** (R1) — é o que torna viável trocar de
  provedor e rotear por tenant.
- **`services/` não importa Streamlit** (R9) — é o que permite a mesma regra servir à API,
  ao mobile e a jobs agendados.

---

## Como executar

```bash
pip install -r requirements.txt
streamlit run app.py
```

No Windows há também o `Iniciar_AgroTop.bat`. O sistema cria um SQLite local
(`agrotop.db`) e popula dados de demonstração se as tabelas estiverem vazias.

### Rodando os testes

```bash
AGROTOP_FORCE_SQLITE=1 python -m unittest discover -s tests -t .
```

⚠️ **O `-t .` não é opcional e o `AGROTOP_FORCE_SQLITE=1` é a segunda trava.** Sem os dois,
os testes podem conectar no banco de **produção** se houver `.streamlit/secrets.toml`
presente. `tests/test_isolamento.py` falha de propósito nesse caso.

---

## Banco de dados

- **SQLite** — padrão local, operação offline, arquivo único.
- **PostgreSQL** — defina `DATABASE_URL`. O sistema traduz placeholders automaticamente.

⚠️ **A tradução cobre pouco.** `_translate()` converte `?` → `%s` e `MAX(0,` →
`GREATEST(0,` — **nada além**. Sintaxe específica de dialeto (`PRAGMA`,
`information_schema`, `chr` vs `char`) precisa de ramo explícito por `USE_PG`. Supor o
contrário derrubou a produção em 2026-08-02; `tests/test_dialeto_duplo.py` existe por causa
disso.

Ao alterar schema, siga [supabase/README.md](supabase/README.md): migration na nuvem → DDL
local → `dump_schema_nuvem.py --baseline` → `testar_baseline.py` → testes.

---

## Credenciais

O banco nasce com `admin` e `op1`, com senhas de `AGROTOP_ADMIN_PASSWORD` e
`AGROTOP_OP_PASSWORD`. Sem as variáveis, senhas aleatórias são geradas e impressas no log.

⚠️ As variáveis valem apenas para **instalações novas** — `_seed_users` só roda com a
tabela `users` vazia. Para trocar a senha de uma conta existente:

```bash
python tools/gerar_hash_senha.py --usuario admin
```

---

## Documentação

| Arquivo | Para quê |
|---|---|
| [ROADMAP.md](ROADMAP.md) | **leia antes de codar** — regras invioláveis, fases, dívidas |
| [DESIGN.md](DESIGN.md) | tokens de cor e convenções de interface |
| [docs/adr/](docs/adr/) | decisões de arquitetura, com o porquê e o que substituem |
| [docs/regulatorio/](docs/regulatorio/) | requisitos do PNIB |
| [specs/](specs/) | tarefas fechadas para delegar a agentes de IA |
| [supabase/README.md](supabase/README.md) | fluxo de alteração de schema |

## Tecnologias

Streamlit · Plotly · Pandas/Numpy · SQLite/PostgreSQL · `openpyxl` e `fpdf2` ·
`shapely`/`pyproj` (geometria de piquetes) · `Pillow`, `opencv-python-headless`,
`pytesseract` (QR e OCR de brinco).
