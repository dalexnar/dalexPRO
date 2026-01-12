# DALEX - Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código
COPY . .

# Crear directorio de datos
RUN mkdir -p /app/data

# Puerto
EXPOSE 8000

# Variables de entorno por defecto
ENV DALEX_MODE=lite
ENV OLLAMA_HOST=http://host.docker.internal:11434
ENV OLLAMA_MODEL=qwen2.5:7b
ENV API_HOST=0.0.0.0
ENV API_PORT=8000

# Comando
CMD ["python", "main.py"]
