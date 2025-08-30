FROM python:3.11-slim

WORKDIR /app

# Dependencias del sistema (solo si las necesitas)
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código al contenedor
COPY . .

# Cloud Run asigna el puerto automáticamente
EXPOSE $PORT

# 👇 IMPORTANTE: usa main:app si tu archivo es main.py
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 main:app

