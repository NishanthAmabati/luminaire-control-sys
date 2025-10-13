FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt --break-system-packages
COPY . scheduler-service/
EXPOSE 6666
CMD ["python3", "-m", "scheduler-service.main"]