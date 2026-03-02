# ---------------------------------------------------------------------------
# Multi-stage Dockerfile for a Django application
#
# Build:  docker build -t myapp .
# Run:    docker run -p 8000:8000 --env-file .env myapp
#
# See .dockerignore to keep the build context small.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Stage 1: Build dependencies and collect static files
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

# Prevent Python from writing .pyc files and enable unbuffered output
# so logs appear immediately in Docker.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System packages needed to build Python C extensions (psycopg2, Pillow, etc.)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        libjpeg62-turbo-dev \
        zlib1g-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy requirements first so pip install is cached unless requirements change.
COPY requirements/production.txt requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code.
COPY . .

# Collect static files during the build so the runtime image does not
# need Node.js or other build tools. The dummy SECRET_KEY is safe here
# because collectstatic does not use it for anything sensitive.
RUN SECRET_KEY=build-placeholder \
    DJANGO_SETTINGS_MODULE=myproject.settings.production \
    python manage.py collectstatic --noinput


# ---------------------------------------------------------------------------
# Stage 2: Runtime image (smaller, no build tools)
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Runtime-only system libraries (no compilers).
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq5 \
        libjpeg62-turbo \
        curl && \
    rm -rf /var/lib/apt/lists/*

# Create a non-root user. Running as root in a container is a security risk.
RUN groupadd --gid 1000 django && \
    useradd --uid 1000 --gid django --shell /bin/bash --create-home django

WORKDIR /app

# Copy installed Python packages from the builder stage.
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code and pre-built static files.
COPY --from=builder /build /app

# Make sure the non-root user owns the application directory.
RUN chown -R django:django /app

USER django

EXPOSE 8000

# Health check so orchestrators (Docker Compose, ECS, Kubernetes) know
# whether the container is alive. Adjust the path to an actual health
# endpoint in your project.
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

# Use exec form so gunicorn receives SIGTERM directly from Docker,
# enabling graceful shutdown. Shell form wraps the process in /bin/sh
# which swallows signals.
CMD ["gunicorn", "myproject.wsgi:application", "-c", "gunicorn.conf.py"]
