# Imagen base ligera con Python 3.11
FROM python:3.11-slim

# Establecer directorio de trabajo
WORKDIR /app

# Instalar dependencias del sistema necesarias
RUN apt-get update && apt-get install -y \
    build-essential \
    libffi-dev \
    libnss3 \
    && rm -rf /var/lib/apt/lists/*

# Copiar dependencias
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código fuente
COPY . .

# Exponer puerto dinámico (Cloud Run asigna $PORT)
EXPOSE $PORT

# Comando de ejecución
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 main:app
