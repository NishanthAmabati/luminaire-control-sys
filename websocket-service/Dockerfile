FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt --break-system-packages
COPY . websocket-service/
EXPOSE 5001
CMD ["python3", "-m", "websocket-service.main"]