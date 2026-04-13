FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=5 \
    CMD python -c "import httpx; r = httpx.get('http://localhost:${PORT:-8000}/health'); exit(0 if r.status_code == 200 else 1)" || exit 1

# Run server - use $PORT injected by Railway, fallback to 8000
CMD uvicorn main:app --host 0.0.0.0 --port $PORT