#!/bin/sh
set -eu

exec gunicorn \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --worker-class uvicorn.workers.UvicornWorker \
  --timeout 600 \
  --access-logfile - \
  --error-logfile - \
  mcp_server_time.http:app
