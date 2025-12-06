FROM python:3.11-slim as build

WORKDIR /app

RUN apt-get update && \
    apt-get install -y build-essential && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

FROM python:3.11-slim as runtime

WORKDIR /app

COPY --from=build /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=build /usr/local/bin /usr/local/bin
COPY --from=build /app /app

RUN adduser --system --no-create-home appuser
USER appuser

EXPOSE 5000

CMD ["python3" , "wsgi.py"]

# The Gunicorn with multiple workers, or migrating to FastAPI, would cause problems
# because the database management is handled completely synchronously in the current setup.
# CMD ["gunicorn", "--workers", "1", "--bind", "0.0.0.0:5000", "wsgi:app"]