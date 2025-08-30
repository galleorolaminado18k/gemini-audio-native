FROM python:3.11-slim

WORKDIR /app

# Dependencias del sistema (solo si las necesitas, si no puedes eliminar esta sección)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código
COPY . .

# Cloud Run fija el puerto por la var $PORT
EXPOSE $PORT

# 👇 IMPORTANTE: apunta a app.py → objeto app
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app
