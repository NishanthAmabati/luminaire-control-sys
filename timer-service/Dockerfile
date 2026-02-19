FROM python:3.11-slim-bookworm AS deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


FROM python:3.11-slim-bookworm AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    jq \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=deps /install /usr/local
ARG APP_PORT
COPY config.yaml /app/config.yaml
COPY . /app/timer_service
EXPOSE $APP_PORT
CMD ["python", "-m", "timer_service.main"]
