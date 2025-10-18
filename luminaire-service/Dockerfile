# stage 1
FROM python:3.11-bookworm AS builder 
WORKDIR /app

# The '-dev' packages are required to compile any C-extensions in the requirements.
RUN apt-get update && \
    apt-get install -y \
    build-essential \
    libffi-dev \
    libssl-dev \
    python3-dev

# Copy requirements.txt and install Python dependencies
COPY requirements.txt .
RUN pip install \
    --no-cache-dir \
    -r requirements.txt

# Copy source code
COPY . luminaire_service

#RUN echo 'import sys, os, runpy; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); runpy.run_module("luminaire_service.main", run_name="__main__")' > start.py

# Compile with PyInstaller using the wrapper

# Compile the Python app with PyInstaller
# --onefile bundles everything into a single executable.
RUN pyinstaller \
    --onefile \
    --clean \
    --noconfirm \
    --name luminaire-service \
    luminaire_service/main.py

# stage 2
FROM debian:bookworm-slim AS runtime

# The minimal runtime libraries PyInstaller often needs:
# libstdc++ is frequently required by Python's C extensions.
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive \
    apt-get install -y \
    --no-install-recommends \
    libstdc++6 \
    ca-certificates \
    curl \
    jq \
    && rm -rf /var/lib/apt/lists/*

RUN adduser --disabled-password --gecos "" appuser
USER appuser
WORKDIR /app

# Copy the binary
COPY --from=builder /app/dist/luminaire-service /app/luminaire-service

EXPOSE 5555 5250

ENTRYPOINT ["/app/luminaire-service"]
