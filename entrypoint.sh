#!/bin/bash
set -e

MODE=${MODE:-backend}

case "$MODE" in
  frontend)
    echo "Starting EXIM Chat Frontend..."
    cd /app/frontend
    exec npm run start
    ;;
  backend)
    echo "Starting EXIM Chat Backend..."
    cd /app
    exec uvicorn main:app --host 0.0.0.0 --port 3333
    ;;
  *)
    echo "Unknown MODE: $MODE. Use 'frontend' or 'backend'"
    exit 1
    ;;
esac
