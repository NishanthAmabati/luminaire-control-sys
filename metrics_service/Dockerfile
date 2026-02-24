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

COPY metrics_service /app/metrics_service
WORKDIR /app/metrics_service

ARG REDIS_URL
ARG METRICS_INTERVAL
ARG METRICS_REDIS_PUB

ENV REDIS_URL=$REDIS_URL \
    METRICS_INTERVAL=$METRICS_INTERVAL \
    METRICS_REDIS_PUB=$METRICS_REDIS_PUB

ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
