FROM python:3.12-slim

WORKDIR /app

# Install Docker CLI for container management
RUN apt-get update && apt-get install -y \
    docker.io \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir pyyaml schedule

# Copy watchdog script
COPY watchdog.py .
COPY config.yaml .

CMD ["python", "-u", "watchdog.py"]
