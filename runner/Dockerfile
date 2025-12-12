FROM python:3.11-slim AS build
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

FROM python:3.11-slim AS runtime
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=build /usr/local/bin /usr/local/bin
COPY --from=build /app /app

EXPOSE 8080

# Run with gunicorn/uvicorn
# TLS is configured via environment variables TLS_ENABLED, TLS_CERT_FILE, TLS_KEY_FILE
CMD ["sh", "-c", "if [ \"$TLS_ENABLED\" = \"true\" ]; then /usr/local/bin/gunicorn -w 1 -k uvicorn.workers.UvicornWorker src.server:app --bind 0.0.0.0:8080 --timeout 120 --certfile $TLS_CERT_FILE --keyfile $TLS_KEY_FILE; else /usr/local/bin/gunicorn -w 1 -k uvicorn.workers.UvicornWorker src.server:app --bind 0.0.0.0:8080 --timeout 120; fi"]