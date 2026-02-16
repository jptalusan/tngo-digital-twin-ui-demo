#!/bin/bash
set -euo pipefail

uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 &
SERVER_PID=$!

cleanup() {
  kill $SERVER_PID || true
}
trap cleanup EXIT

until curl --output /dev/null --silent --head --fail http://127.0.0.1:8000/openapi.json; do
  sleep 1
done

curl http://127.0.0.1:8000/openapi.json -o openapi.json
npx redoc-cli bundle openapi.json -o openapi.html

echo "API documentation generated at openapi.html"
