# Use official lightweight Python image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# Set working directory
WORKDIR /app

# Install system dependencies needed for Prisma client binaries, Node/npm, and PostgreSQL connections
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    openssl \
    libatomic1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Generate Prisma client locally inside the container filesystem
RUN prisma generate

# Expose backend port
EXPOSE 8000

# Run uvicorn server (automatically sync database schema on startup)
CMD ["sh", "-c", "prisma db push && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
