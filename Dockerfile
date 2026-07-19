# Official lightweight Python image
FROM python:3.11-slim

# Setting environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# Setting working directory
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    openssl \
    libatomic1 \
    && rm -rf /var/lib/apt/lists/*

# Copying requirements and installing python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copying project files
COPY . .

# Generating Prisma client locally inside the container filesystem
RUN prisma generate
RUN mkdir -p /app/uploads/blog

# Exposing backend port
EXPOSE 8000

# ── Container health check (30s) ────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]