# Multi-stage build for Glovebox ZMK keyboard firmware management tool
FROM python:3.11-slim as builder

# Install system dependencies for building
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml uv.lock README.md ./
COPY glovebox/ ./glovebox/

# Install dependencies and build
RUN uv sync --frozen --no-install-project --no-dev
RUN uv build

# Production stage
FROM python:3.11-slim

# Install system dependencies for runtime
# Docker is needed for firmware compilation, USB tools for flashing
RUN apt-get update && apt-get install -y \
    docker.io \
    udev \
    usbutils \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for runtime
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Create non-root user for security
RUN groupadd -r glovebox && useradd -r -g glovebox -s /bin/bash glovebox

# Create application directory
WORKDIR /app

# Copy built package from builder stage
COPY --from=builder /app/dist/*.whl /tmp/

# Install the application
RUN uv pip install --system /tmp/*.whl && rm /tmp/*.whl

# Create directories for user data
RUN mkdir -p /home/glovebox/.glovebox /workspace && \
    chown -R glovebox:glovebox /home/glovebox /workspace

# Add glovebox user to docker group for firmware compilation
RUN usermod -aG docker glovebox

# Switch to non-root user
USER glovebox

# Set up environment
ENV HOME=/home/glovebox
ENV PATH=/home/glovebox/.local/bin:$PATH
ENV GLOVEBOX_CONFIG_DIR=/home/glovebox/.glovebox
ENV GLOVEBOX_WORKSPACE_DIR=/workspace

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import glovebox; print('OK')" || exit 1

# Default working directory for user operations
WORKDIR /workspace

# Entry point
ENTRYPOINT ["python", "-m", "glovebox.cli"]
CMD ["--help"]