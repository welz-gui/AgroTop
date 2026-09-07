# Spec 0081 — Dockerfile do app web (AgroTop/Streamlit)

- **Tipo:** implementação · **Risco:** baixo · **Esforço:** meio dia a 1 dia
- **Branch:** `feat/dockerfile-app-web`
- **Altere:** `Dockerfile` (novo, raiz), `.dockerignore` (novo, raiz) e a documentação de
  como rodar (`README.md`/`NOTAS_SESSAO.md`, o que já existir sobre "como rodar o app")
- **Pré-requisito:** nenhum — a portabilidade já foi garantida pela
  [ADR 0002](docs/adr/0002-fronteira-de-portabilidade.md) (acesso ao banco é
  `psycopg2`/`DATABASE_URL`, sem SDK de nenhuma nuvem)

---

## Objetivo

`docs/revisao-relatorio-arquitetura-2026-08.md` §7 lista **"containerizar" (item 5)** e
**"sair do Streamlit Community Cloud" (item 6)** como as duas últimas melhorias
pendentes — e o item 5 é pré-requisito do item 6: **"destrava qualquer alvo de
hospedagem"**. Sem um `Dockerfile`, nenhuma migração de hospedagem (Fly.io, Cloud Run, ou
qualquer outra) é possível.

Esta spec entrega **só** o container do app web (`app.py`, Streamlit) — rodável local e
publicável em qualquer host que aceite uma imagem Docker com uma porta HTTP exposta.
**Não decide qual host usar** — isso é decisão do mantenedor, feita fora desta spec; o
Dockerfile resultante deve funcionar igual em Fly.io, Cloud Run ou em `docker run` local,
sem *build args* específicos de plataforma.

## Contexto que você precisa

- **Python 3.12** — é a versão do CI (`.github/workflows/ci.yml`), use a mesma na imagem
  para não introduzir uma segunda combinação de versões nunca testada.
- **`requirements.txt`** da raiz tem dependências com binários nativos que **não** vêm
  prontos num `python:3.12-slim` puro:
  - `opencv-python-headless` — a variante "headless" evita a maior parte das libs gráficas
    do X11, mas ainda depende de `libglib2.0-0` no runtime Debian/Ubuntu.
  - `pytesseract` (`app.py::_ocr_number`, linha ~344) — é só o *wrapper* Python; o binário
    **`tesseract-ocr`** precisa estar instalado no sistema, senão todo OCR de brinco falha
    em silêncio (o `try/except Exception` de `_ocr_number` engole o erro e devolve `None`
    — bom para não quebrar a tela, ruim para notar que faltou o pacote do sistema).
    A chamada usa `tessedit_char_whitelist=0123456789` (só dígitos) — o pacote de idioma
    **padrão (inglês) já basta**, não instale `tesseract-ocr-por` só por causa disto; se
    descobrir outro uso de OCR que precise de português, documente no PR.
  - `rasterio` (spec 0079, `services/ndvi.py`) e `pyproj`/`shapely` (`services/geometria.py`)
    — as wheels `manylinux` do PyPI para Linux x86_64 já trazem GDAL/PROJ/GEOS embutidos;
    **não devem** exigir `apt-get install gdal-bin` à parte, mas **confirme isto rodando o
    build** (critério de aceite 3) em vez de assumir.
- **`.streamlit/config.toml`** já define `[server] port = 8501`, mas `[browser]
  serverAddress = "localhost"` é só para exibir a URL no terminal — **não** controla em
  qual endereço o Streamlit escuta. Dentro de um container, o processo precisa escutar em
  `0.0.0.0`, senão fica inacessível de fora — isso é `--server.address=0.0.0.0` (flag de
  CLI ou `STREAMLIT_SERVER_ADDRESS=0.0.0.0`), **não** uma edição do `config.toml`.
- **`.streamlit/secrets.toml` está no `.gitignore`** e contém, hoje, a string de conexão
  real de produção (`DATABASE_URL`) — **nunca** `COPY` esse arquivo para dentro da
  imagem. A imagem recebe `DATABASE_URL` (e qualquer outro segredo) **por variável de
  ambiente**, injetada pelo host de destino (Fly `secrets set`, Cloud Run env var, etc.),
  igual ao padrão que `repositories/conexao.py::_conn()` já espera (`os.environ`).
- **`.dockerignore` importa tanto quanto o `Dockerfile`**: sem ele, `mobile/`
  (projeto Flutter inteiro, com `build/`), `poc/`, `.venv/`, `.git/` e os `__pycache__/`
  entram no contexto de build e infla a imagem por nada — nenhum desses diretórios é
  necessário para rodar `app.py`.
- **Health check:** a versão do Streamlit em uso (`streamlit>=1.37.0`) expõe
  `/_stcore/health` — **confirme contra o container rodando** (`curl` local, critério de
  aceite 4) antes de fixar esse caminho no `HEALTHCHECK`; não assuma sem testar, versões
  diferentes do Streamlit já mudaram esse caminho no passado (`/healthz` era o antigo).
- **`backend_api/` fica de fora desta spec.** Tem seu próprio `requirements.txt`, roda em
  processo separado (`uvicorn`), e a hospedagem dele já está registrada como "decisão
  operacional pendente" em `ROADMAP.md` (linha ~482), à parte da hospedagem do web. Se/quando
  fizer sentido containerizar a API, é spec própria.

## Contrato obrigatório

1. **`Dockerfile` multi-stage** (builder + runtime), raiz do repo:
   - Estágio de build: `python:3.12-slim`, instala dependências de compilação só se
     necessárias (confira antes de adicionar — muitas wheels do `requirements.txt` já são
     binárias, não precisam de `gcc`/`build-essential`).
   - Estágio final: `python:3.12-slim` limpo, copia só o necessário do estágio de build
     (pacotes instalados) + o código da aplicação, e instala via `apt-get` apenas os pacotes
     de sistema realmente exigidos em runtime (ex.: `tesseract-ocr`, `libglib2.0-0`, se o
     critério de aceite 3 confirmar que são necessários) — `apt-get clean` e remoção de
     listas de pacote na mesma camada, para não inflar a imagem.
   - `EXPOSE 8501`.
   - `CMD` roda `streamlit run app.py --server.address=0.0.0.0 --server.port=8501
     --server.headless=true` (headless já está em `config.toml`, mas repita explícito no
     `CMD` — clareza sobre o que o container realmente executa, sem depender de o arquivo
     de config estar íntegro no ambiente de destino).
   - `HEALTHCHECK` usando o caminho confirmado pelo critério de aceite 4.
2. **`.dockerignore`** excluindo no mínimo: `.git/`, `.venv/`, `mobile/`, `poc/`,
   `__pycache__/`, `*.pyc`, `.streamlit/secrets.toml`, `tests/`, `backend_api/` (não é
   usado pelo `app.py`, não precisa ir na imagem do web).
3. **Nenhuma alteração em `app.py`, `database.py`, `services/`, `repositories/`** — esta
   spec só empacota o que já existe e funciona.

## Critério de aceite

1. `docker build -t agrotop-web .` conclui sem erro.
2. `docker run -e DATABASE_URL=<sqlite ou postgres de teste> -p 8501:8501 agrotop-web`
   sobe o processo e o Streamlit fica acessível em `http://localhost:8501` de fora do
   container (prova de que `--server.address=0.0.0.0` está funcionando de fato, não só
   presente no comando).
3. **Rode pelo menos uma tela que usa cada dependência nativa citada** (câmera/OCR de
   brinco, mapa com polígono, e a seção de NDVI da spec 0079) dentro do container e
   confirme que nenhuma delas falha por biblioteca de sistema ausente — cole no PR qual
   pacote `apt-get` acabou sendo necessário para cada uma, ou confirme que nenhum foi
   necessário.
4. `curl` (de fora do container) contra o caminho de health check declarado no
   `HEALTHCHECK` devolve 200 — cole o comando e a resposta no PR.
5. Tamanho final da imagem (`docker images agrotop-web`) documentado no PR — não há meta
   numérica aqui (é a primeira medição), mas registre o número para servir de baseline a
   mudanças futuras.
6. `git diff --stat` do PR não toca em nenhum arquivo fora de `Dockerfile`,
   `.dockerignore` e documentação — nenhuma linha de `app.py`/`database.py`/`services/`/
   `repositories/` muda.

## Proibições

- ❌ Não copie `.streamlit/secrets.toml` para dentro da imagem, nem grave `DATABASE_URL`
  (ou qualquer segredo) como `ENV` fixo no `Dockerfile` — é exatamente o erro que o
  ROADMAP (R19) já proíbe para chave de API, e vale igual para string de conexão de banco.
- ❌ Não containerize `backend_api/` nesta spec — hospedagem da API é decisão à parte,
  já registrada como pendente no ROADMAP.
- ❌ Não escolha nem configure um host de nuvem específico (Fly, Cloud Run, Render...) —
  esta spec entrega só a imagem; a escolha de onde publicá-la é decisão separada do
  mantenedor.
- ❌ Não adicione `docker-compose.yml` nem orquestração — fora de escopo; um único
  `Dockerfile` publicável já resolve o item 5 do §7 da revisão de arquitetura.
- ❌ Não mude nenhuma lógica de `app.py`/`database.py`/`services/`/`repositories/` — se o
  build revelar um bug real de código (improvável, mas já aconteceu antes com
  containerização de outros projetos desta base), documente e abra separado; não misture
  no mesmo PR.
- ❌ Não instale pacote de sistema "por precaução" sem confirmar que é necessário
  (critério de aceite 3) — cada `apt-get install` extra é peso permanente na imagem.

## Como verificar antes de abrir o PR

```bash
docker build -t agrotop-web .
docker run --rm -e DATABASE_URL=sqlite:///./teste.db -p 8501:8501 agrotop-web &
sleep 5
curl -sI http://localhost:8501/_stcore/health   # ou o caminho confirmado no critério 4
docker images agrotop-web --format "{{.Size}}"
```

## Entrega

PR para `main`, pronto para revisão. Cole no corpo: o tamanho final da imagem, o resultado
do `curl` de health check, e quais pacotes `apt-get` (se algum) foram realmente
necessários para cada dependência nativa testada no critério de aceite 3.
