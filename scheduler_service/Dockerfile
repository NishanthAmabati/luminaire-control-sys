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

COPY scheduler_service /app/scheduler_service
WORKDIR /app/scheduler_service

ARG REDIS_URL
ARG TIMEZONE
ARG SCHEDULER_SCENES_DIR
ARG SCHEDULER_INTERVAL
ARG SCHEDULER_REDIS_PUB
ARG STATE_REDIS_PUB
ARG SCHEDULER_LUMINAIRE_URL
ARG SCALES_CCT_MIN
ARG SCALES_CCT_MAX
ARG SCALES_LUX_MIN
ARG SCALES_LUX_MAX

ENV REDIS_URL=$REDIS_URL \
    TIMEZONE=$TIMEZONE \
    SCHEDULER_SCENES_DIR=$SCHEDULER_SCENES_DIR \
    SCHEDULER_INTERVAL=$SCHEDULER_INTERVAL \
    SCHEDULER_REDIS_PUB=$SCHEDULER_REDIS_PUB \
    STATE_REDIS_PUB=$STATE_REDIS_PUB \
    SCHEDULER_LUMINAIRE_URL=$SCHEDULER_LUMINAIRE_URL \
    SCALES_CCT_MIN=$SCALES_CCT_MIN \
    SCALES_CCT_MAX=$SCALES_CCT_MAX \
    SCALES_LUX_MIN=$SCALES_LUX_MIN \
    SCALES_LUX_MAX=$SCALES_LUX_MAX

ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
