FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt --break-system-packages
COPY . luminaire-service/
EXPOSE 5555 5250
CMD ["python3", "-m", "luminaire-service.main"]