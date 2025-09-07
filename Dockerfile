FROM python:3.10
WORKDIR /app
COPY . .

RUN apt-get update && \
    apt-get install -y chromium-driver chromium && \
    rm -rf /var/lib/apt/lists/*

RUN pip install -r requirements.txt
CMD ["python", "app.py"]
