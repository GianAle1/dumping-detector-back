#!/bin/bash

echo "Inicializando Superset..."
superset db upgrade
superset fab create-admin \
  --username $ADMIN_USERNAME \
  --firstname $ADMIN_FIRST_NAME \
  --lastname $ADMIN_LAST_NAME \
  --email $ADMIN_EMAIL \
  --password $ADMIN_PASSWORD || true
superset init
