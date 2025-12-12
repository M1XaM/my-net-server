FROM python:3.11-slim

WORKDIR /app

# Install only the minimal HTTP server dependency
RUN pip install --no-cache-dir flask==3.0.0 gunicorn==22.0.0

COPY executor.py /app/executor.py

# Run as non-root user for additional security
RUN useradd -m -s /bin/bash sandboxuser
USER sandboxuser

EXPOSE 8000

CMD ["gunicorn", "-w", "1", "-b", "0.0.0.0:8000", "executor:app", "--timeout", "30"]
