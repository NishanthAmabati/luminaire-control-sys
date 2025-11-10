# stage 1
FROM python:3.11-bookworm AS builder
WORKDIR /app

ARG APP_NAME
ARG MAIN_MODULE

RUN apt-get update && \
    apt-get install -y \
    build-essential \
    libffi-dev \
    libssl-dev \
    python3-dev

COPY requirements.txt .
RUN pip wheel --no-cache-dir -r requirements.txt -w /wheels
RUN pip install --no-cache-dir --find-links=/wheels -r requirements.txt

COPY . ./monitoring_service

RUN pyinstaller \
    --onefile \
    --clean \
    --noconfirm \
    --name ${APP_NAME} \
    ${MAIN_MODULE}

# stage 2
FROM debian:bookworm-slim AS runtime
ARG APP_USER
ARG APP_NAME
ARG APP_PORT

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && DEBIAN_FRONTEND=noninteractive \
    apt-get install -y --no-install-recommends \
    libstdc++6 ca-certificates curl jq net-tools inetutils-telnet iputils-ping \
    sudo \
    && rm -rf /var/lib/apt/lists/*

RUN adduser --disabled-password --gecos "" $APP_USER \
    && echo "$APP_USER ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers
    
USER $APP_USER
WORKDIR /app

COPY --from=builder /app/dist/${APP_NAME} /app/${APP_NAME}

EXPOSE ${APP_PORT}
ENTRYPOINT ["/app/monitoring-service"]