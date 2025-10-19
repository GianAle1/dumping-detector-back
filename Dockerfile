# Imagen base con Python 3.10 (compatible con todas tus dependencias)
FROM python:3.10

# Instalar dependencias del sistema necesarias para Selenium y ML
RUN apt-get update && \
    apt-get install -y chromium-driver chromium && \
    rm -rf /var/lib/apt/lists/*

# Crear usuario sin privilegios
RUN useradd -ms /bin/bash appuser

# Crear carpeta de trabajo
WORKDIR /app

# Copiar todo el proyecto
COPY . .

# Instalar dependencias Python
RUN pip install --no-cache-dir -r requirements.txt

# Crear carpetas necesarias (logs, cache, modelos)
RUN mkdir -p logs cache ml/data && \
    chown -R appuser:appuser logs cache ml data

# Cambiar a usuario normal
USER appuser

# Exponer puerto del servidor Flask
EXPOSE 5000

# Comando por defecto
CMD ["python", "app.py"]
