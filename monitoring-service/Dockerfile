FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt --break-system-packages
COPY . monitoring-service/
EXPOSE 7777
CMD ["python3", "-m", "monitoring-service.main"]