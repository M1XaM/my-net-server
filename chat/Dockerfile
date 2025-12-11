FROM python:3.11-slim as build

WORKDIR /app

RUN apt-get update && \
    apt-get install -y build-essential libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

FROM python:3.11-slim as runtime

WORKDIR /app

# Install libpq for psycopg2 runtime
RUN apt-get update && \
    apt-get install -y libpq5 && \
    rm -rf /var/lib/apt/lists/*

COPY --from=build /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=build /usr/local/bin /usr/local/bin
COPY --from=build /app /app

RUN adduser --system --no-create-home appuser
USER appuser

EXPOSE 5000

# Run with uvicorn for full async support
# Workers can be increased since we're now fully async
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5000", "--workers", "1"]