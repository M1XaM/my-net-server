FROM python:3.11-slim AS build
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

FROM python:3.11-slim AS runtime
WORKDIR /app

COPY --from=build /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=build /usr/local/bin /usr/local/bin
COPY --from=build /app /app

EXPOSE 8080

CMD ["/usr/local/bin/gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "src.server:app", "--bind", "0.0.0.0:8080"]