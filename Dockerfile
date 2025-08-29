FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema si son necesarias
RUN apt-get update && apt-get install -y \
    && rm -rf /var/lib/apt/lists/*

# Copiar e instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copiar aplicación
COPY . .

# Exponer puerto dinámico asignado por Google Cloud Run
EXPOSE $PORT

# Comando para ejecutar
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 main:app
