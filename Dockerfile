# ============================================
# Stage 1: Dependencies
# ============================================
FROM python:3.13-slim AS deps
WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc default-libmysqlclient-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ============================================
# Stage 2: Builder (dev full install)
# ============================================
FROM python:3.13-slim AS builder
WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc default-libmysqlclient-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# ============================================
# Stage 3: Production Runner
# ============================================
FROM python:3.13-slim AS runner
WORKDIR /app

# Install MySQL client library (runtime only, no dev headers).
RUN apt-get update && \
    apt-get install -y --no-install-recommends default-libmysqlclient-dev curl && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user.
ARG APP_UID=1000
ARG APP_GID=1000
RUN groupadd --gid ${APP_GID} appuser && \
    useradd --uid ${APP_UID} --gid ${APP_GID} --create-home appuser

# Copy Python packages from deps stage.
COPY --from=deps /install /usr/local

# Copy application code.
COPY --chown=appuser:appuser . .

USER appuser

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 9092
EXPOSE 5053/udp

HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:9092/health || exit 1

# Default: run REST API server.
CMD ["python", "-m", "uvicorn", "app.rest_server:app", "--host", "0.0.0.0", "--port", "9092"]
