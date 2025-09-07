FROM python:3.10

RUN apt-get update && \
    apt-get install -y chromium-driver chromium && \
    rm -rf /var/lib/apt/lists/*

RUN useradd -ms /bin/bash appuser

WORKDIR /app
COPY . .

RUN pip install -r requirements.txt && \
    mkdir -p logs cache && \
    chown -R appuser:appuser logs cache

USER appuser

CMD ["python", "app.py"]
