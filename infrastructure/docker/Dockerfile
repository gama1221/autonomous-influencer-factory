# Build stage
FROM python:3.11-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast Python package management
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Create virtual environment and install dependencies
RUN uv venv && \
    . /app/.venv/bin/activate && \
    uv sync --frozen --no-dev

# Production stage
FROM python:3.11-slim AS production

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev \
    curl \
    gnupg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Google Cloud SDK for GCS access (optional)
RUN echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | \
    tee -a /etc/apt/sources.list.d/google-cloud-sdk.list && \
    curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | \
    apt-key --keyring /usr/share/keyrings/cloud.google.gpg add - && \
    apt-get update && apt-get install -y \
    google-cloud-sdk \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r chimera && useradd -r -g chimera chimera

# Set working directory
WORKDIR /app

# Copy Python virtual environment from builder
COPY --from=builder /app/.venv .venv
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/logs /app/data /app/uploads && \
    chown -R chimera:chimera /app && \
    chmod -R 755 /app

# Switch to non-root user
USER chimera

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import sys; import urllib.request; \
    try: urllib.request.urlopen('http://localhost:8000/health').read(); \
    sys.exit(0) except: sys.exit(1)"

# Expose port
EXPOSE 8000

# Runtime configuration
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENVIRONMENT=production \
    UV_PYTHON_PREFER_SYSTEM=1

# Run the application
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]