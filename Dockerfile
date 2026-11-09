FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM ghcr.io/astral-sh/uv:0.13.6 AS uv

FROM python:3.13-slim-bookworm
COPY --from=uv /uv /usr/local/bin/uv
COPY --from=frontend /usr/local/bin/node /usr/local/bin/node
COPY --from=frontend /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && npm install -g @fly-ai/flyai-cli@1.0.16 \
    && npm cache clean --force
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY agent.py app.py replies.py settings.py trip.py instructions.md ./
COPY skills/ ./skills/
COPY --from=frontend /build/dist ./frontend/dist
RUN useradd --create-home traveler \
    && mkdir /app/data \
    && chown -R traveler:traveler /app
USER traveler
EXPOSE 7932
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7932/api/health', timeout=3)"]
CMD ["uvicorn", "app:create_app", "--factory", "--host", "0.0.0.0", "--port", "7932", "--workers", "1"]
