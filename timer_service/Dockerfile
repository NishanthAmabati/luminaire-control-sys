FROM python:3.11-slim-bookworm AS deps

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt /app/requirements.txt
COPY app_logging /app/app_logging
RUN pip install --no-cache-dir --prefix=/install -r /app/requirements.txt

FROM python:3.11-slim-bookworm AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    jq \
    tzdata \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=deps /install /usr/local

COPY timer_service /app/timer_service
COPY --from=deps /app/app_logging /app/timer_service/app_logging
WORKDIR /app/timer_service

ARG REDIS_URL
ARG TIMEZONE
ARG TIMER_REDIS_PUB
ARG STATE_REDIS_PUB
ARG TIMER_STATE_SERVICE_URL

ENV REDIS_URL=$REDIS_URL \
    TIMEZONE=$TIMEZONE \
    TZ=$TIMEZONE \
    TIMER_REDIS_PUB=$TIMER_REDIS_PUB \
    STATE_REDIS_PUB=$STATE_REDIS_PUB \
    TIMER_STATE_SERVICE_URL=$TIMER_STATE_SERVICE_URL

ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
