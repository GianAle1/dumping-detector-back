# Dumping Detector Backend

## Ejecución de tareas en segundo plano

Este proyecto utiliza [Celery](https://docs.celeryq.dev/) para ejecutar el
scraper de forma asíncrona.

### Instalación

Requiere Python 3.10–3.12 y Celery 5.3.4. Celery 5.5 no funciona en Python 3.13.

```bash
pip install -r requirements.txt
```

### Docker (opcional)

Para evitar problemas de compatibilidad, puedes ejecutar el proyecto con Docker (Python 3.10):

```bash
docker-compose up --build
```

### Variables de entorno

Antes de iniciar la aplicación o los workers, define las siguientes variables de entorno:

- `DEBUG`: activa el modo de depuración de Flask (`True` o `False`, por defecto `False`).
- `CELERY_BROKER_URL`: URL del broker de mensajes para Celery.
- `CELERY_RESULT_BACKEND`: URL del backend de resultados para Celery.
- `ALLOWED_ORIGINS`: lista separada por comas de dominios permitidos para CORS (usa `*` para permitir todos).

### Levantar los servicios

1. Inicia un broker y backend de resultados, por ejemplo Redis:

   ```bash
   redis-server
   ```

2. Ejecuta un worker de Celery:

   ```bash
   celery -A tasks worker --loglevel=info
   ```

3. Inicia la aplicación Flask:

   ```bash
   python app.py
   ```

### Uso de los endpoints

1. Encola una tarea de scraping:

   ```bash
   curl -X POST http://localhost:5000/api/scrape \
        -H "Content-Type: application/json" \
        -d '{"producto": "zapatos", "plataforma": "aliexpress"}'
   ```

   La respuesta contendrá un `task_id`.

2. Consulta el estado y resultado de la tarea:

   ```bash
   curl http://localhost:5000/api/resultado/<task_id>
   ```

   Cuando la tarea haya finalizado, el objeto resultante incluirá los
   productos encontrados y el nombre del archivo CSV generado.

