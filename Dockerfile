FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (separate layer so rebuilds are fast)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Ensure the data directory exists inside the image
RUN mkdir -p /app/data

EXPOSE 8000

# Health check — Docker will mark the container unhealthy if the app stops responding
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
