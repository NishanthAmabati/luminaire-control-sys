FROM python:3.11-slim-bookworm AS deps

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --prefix=/install -r /app/requirements.txt

FROM python:3.11-slim-bookworm AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    jq \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=deps /install /usr/local

COPY state_service /app/state_service
WORKDIR /app/state_service

ARG REDIS_URL
ARG STATE_API_HOST
ARG STATE_API_PORT
ARG STATE_API_LOOP
ARG STATE_API_LOG_LEVEL
ARG STATE_API_ACCESS_LOG
ARG CORS_ORIGINS
ARG STATE_REDIS_PUB
ARG SCHEDULER_REDIS_PUB
ARG METRICS_REDIS_PUB

ENV REDIS_URL=$REDIS_URL \
    STATE_API_HOST=$STATE_API_HOST \
    STATE_API_PORT=$STATE_API_PORT \
    STATE_API_LOOP=$STATE_API_LOOP \
    STATE_API_LOG_LEVEL=$STATE_API_LOG_LEVEL \
    STATE_API_ACCESS_LOG=$STATE_API_ACCESS_LOG \
    CORS_ORIGINS=$CORS_ORIGINS \
    STATE_REDIS_PUB=$STATE_REDIS_PUB \
    SCHEDULER_REDIS_PUB=$SCHEDULER_REDIS_PUB \
    METRICS_REDIS_PUB=$METRICS_REDIS_PUB

ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
