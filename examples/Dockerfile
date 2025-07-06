# Multi-stage build for Ruuvi Sensor Service
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    bluetooth \
    bluez \
    libbluetooth-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    bluetooth \
    bluez \
    bluez-tools \
    dbus \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create application user
RUN groupadd -r ruuvi && useradd -r -g ruuvi ruuvi

# Create application directory
WORKDIR /app

# Copy application files
COPY src/ ./src/
COPY main.py .
COPY .env.sample .env

# Create data and logs directories
RUN mkdir -p data logs && \
    chown -R ruuvi:ruuvi /app

# Set up Bluetooth permissions
RUN usermod -a -G bluetooth ruuvi

# Health check script
COPY examples/healthcheck.py ./healthcheck.py
RUN chmod +x healthcheck.py

# Expose any ports if needed (none for this service)
# EXPOSE 8080

# Environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python healthcheck.py

# Switch to non-root user
USER ruuvi

# Default command
CMD ["python", "main.py", "--monitor"]