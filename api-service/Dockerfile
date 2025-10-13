FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt --break-system-packages
COPY . api-service/
EXPOSE 8888
CMD ["python3", "-m", "api-service.main"]