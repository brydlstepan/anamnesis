# syntax=docker/dockerfile:1

# ---------- frontend build ----------
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------- runtime ----------
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ANAMNESIS_DATA_DIR=/data \
    ANAMNESIS_STATIC_DIR=/app/static

ARG UID=1000
ARG GID=1000
RUN groupadd -g ${GID} anamnesis && useradd -u ${UID} -g ${GID} -M -d /app -s /usr/sbin/nologin anamnesis

WORKDIR /app
COPY backend/pyproject.toml ./backend/
COPY backend/anamnesis ./backend/anamnesis
RUN pip install ./backend && rm -rf ./backend
COPY --from=web /web/dist /app/static

RUN mkdir -p /data /config /import && chown -R anamnesis:anamnesis /data /config
VOLUME ["/data", "/config"]
USER anamnesis
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/api/v1/health', timeout=4).status == 200 else 1)"

CMD ["anamnesis", "serve", "--host", "0.0.0.0", "--port", "8080"]
