# Multi-stage Dockerfile adapted from GameArena style

# ============================================
# Stage 1: Build frontend (Node.js)
# ============================================
FROM node:18-bullseye-slim AS frontend-builder

WORKDIR /app/frontend

# Copy package files and install dependencies reproducibly
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund --silent

# Copy frontend sources and build
COPY frontend/ ./
ARG VITE_API_BASE=""
ENV VITE_API_BASE=${VITE_API_BASE}
RUN npm run build --silent

# ============================================
# Stage 2: Python runtime
# ============================================
FROM python:3.11-slim

LABEL maintainer="FunGame Team"
LABEL description="FunGame - Flask + React + PixiJS"
LABEL version="1.0.0"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FLASK_ENV=production \
    PORT=5000

WORKDIR /app

# Install minimal system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl gcc ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python requirements
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Create a non-root user for running the app
RUN useradd -m -u 1000 fungame || true && mkdir -p /app && chown -R fungame:fungame /app

# Copy application sources into the image and set ownership
# Use --chown so files are owned by the non-root user
COPY --chown=fungame:fungame ./. ./

# Copier le frontend buildé depuis le stage 1
COPY --from=frontend-builder --chown=fungame:fungame /app/frontend/dist ./static

# Copy built frontend from builder into ./frontend/dist so app can serve it
COPY --from=frontend-builder --chown=fungame:fungame /app/frontend/dist/ ./frontend/dist/

# Create runtime directories with proper ownership
RUN mkdir -p /app/logs && chown -R fungame:fungame /app/logs

# Switch to non-root user
USER fungame

EXPOSE 5000

# Healthcheck (runs as container user; use curl if installed)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["sh", "-c", "curl -f http://127.0.0.1:5000/api || exit 1"]

# Start the application
CMD ["gunicorn", "-k", "eventlet", "-w", "1", "--bind", "0.0.0.0:5000", "wsgi:app"]
