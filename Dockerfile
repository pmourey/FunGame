# Multi-stage build: build frontend with Node then build a Python image that serves the Flask backend

# 1) Frontend build stage
FROM node:18-alpine AS frontend-builder
WORKDIR /build/frontend
# Install dependencies first (use package-lock when present)
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --silent
COPY frontend/ .
RUN npm run build --silent

# 2) Backend final image
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app

# System deps (if any are required by packages, keep minimal)
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install (project has requirements.txt at repo root)
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend sources (files are at repo root)
COPY ./. ./

# Copy built frontend into project frontend/dist so Flask (which expects repo_root/frontend/dist) can serve it
COPY --from=frontend-builder /build/frontend/dist/ ./frontend/dist/

# Expose port used by Flask app
EXPOSE 5000

# Run the Flask app (app.py at repo root is the entrypoint)
CMD ["python", "app.py"]
