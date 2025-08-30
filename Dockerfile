FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema mínimas
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código de la app
COPY . .

# Cloud Run asigna el puerto en la variable $PORT
EXPOSE $PORT

# Arrancar el servidor con Gunicorn apuntando al objeto app en app.py
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app
