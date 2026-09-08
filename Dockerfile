# ==============================================================================
# Estágio 1 — Builder: Instala dependências Python em ambiente virtual isolado
# ==============================================================================
FROM python:3.12-slim AS builder

WORKDIR /app

# Cria virtualenv isolado em /opt/venv
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .

# Todas as dependências possuem wheels pré-compiladas (manylinux); não é necessário gcc/build-essential
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ==============================================================================
# Estágio 2 — Runtime: Imagem final mínima com binários de sistema estritamente necessários
# ==============================================================================
FROM python:3.12-slim AS runner

# Pacotes nativos de sistema estritamente necessários:
# - libexpat1: dependência de sistema exigida pelo rasterio (libexpat.so.1)
# - tesseract-ocr: binário para OCR de brincos (pytesseract em app.py);
#                  traz automaticamente libglib2.0-0t64 transitivamente (OpenCV headless)
# - curl: utilizado pelo HEALTHCHECK para sondar o endpoint de saúde do Streamlit
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        libexpat1 \
        tesseract-ocr \
        curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copia ambiente virtual pré-construído do estágio builder
COPY --from=builder /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true

# Copia código da aplicação (ignora testes, mobile, secrets via .dockerignore)
COPY . .

# 8501 é o padrão do Streamlit — o que `docker run -p 8501:8501` e o
# fly.toml esperam. Mas plataformas como o Cloud Run injetam a própria
# porta via a variável $PORT (ex.: 8080) e exigem que o container escuta
# exatamente nela, senão o healthcheck da plataforma nunca vê o container
# subir (achado real: testado contra um deploy de teste no Cloud Run em
# 2026-09-08, revisão anterior deste Dockerfile falhava por isso). CMD e
# HEALTHCHECK abaixo usam forma shell (sem colchetes) de propósito — é o
# que permite `${PORT:-8501}` expandir; caem para 8501 quando $PORT não
# existir (docker run local, Fly.io).
EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f "http://localhost:${PORT:-8501}/_stcore/health" || exit 1

CMD streamlit run app.py --server.address=0.0.0.0 --server.port=${PORT:-8501} --server.headless=true
