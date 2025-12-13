# =============================================================================
# EXIM Chat - Single Image (Multi-Mode)
# =============================================================================
# One image that can run as either frontend or backend
# Usage:
#   - Frontend: docker run -e MODE=frontend -p 3000:3000 ghcr.io/prb-naoby/exim-chat
#   - Backend:  docker run -e MODE=backend -p 3333:3333 ghcr.io/prb-naoby/exim-chat
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Build Frontend
# -----------------------------------------------------------------------------
FROM node:20-alpine AS frontend-builder

WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci

COPY frontend/ .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# -----------------------------------------------------------------------------
# Stage 2: Combined Runtime
# -----------------------------------------------------------------------------
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice \
    fonts-liberation \
    curl \
    bash \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application code
COPY . .

# Copy built frontend from builder stage
COPY --from=frontend-builder /frontend/.next ./frontend/.next
COPY --from=frontend-builder /frontend/public ./frontend/public
COPY --from=frontend-builder /frontend/node_modules ./frontend/node_modules
COPY --from=frontend-builder /frontend/package.json ./frontend/package.json

# Create data and logs directories
RUN mkdir -p /app/data /app/logs

# Copy and setup entrypoint script
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Default to backend mode
ENV MODE=backend

# Expose both ports (only one will be used depending on mode)
EXPOSE 3000 3333

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:3333/ || curl -f http://localhost:3000/ || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
