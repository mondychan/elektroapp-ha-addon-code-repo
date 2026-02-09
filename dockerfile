# Stage 1: build React frontend (build on host platform to avoid qemu issues)
ARG BUILDPLATFORM
ARG TARGETPLATFORM
FROM --platform=$BUILDPLATFORM node:22-alpine AS frontend-builder
WORKDIR /app
COPY app/frontend/package*.json ./
RUN npm install
COPY app/frontend/ ./
RUN npm run build

# Stage 2: Python backend
FROM python:3.14-slim
WORKDIR /app
COPY app/backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Zkopíruj React build do backendu
COPY --from=frontend-builder /app/build ./frontend_build

# Zkopíruj backend soubory
COPY app/backend/ ./

# Expose port
EXPOSE 8000

# Start backend
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
