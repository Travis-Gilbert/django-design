"""
Gunicorn configuration for a Django application.

Usage:
    gunicorn myproject.wsgi:application -c gunicorn.conf.py

This configuration reads from environment variables so the same file
works across staging, production, and local Docker environments.
"""

import multiprocessing
import os


# ---------------------------------------------------------------------------
# Server socket
# ---------------------------------------------------------------------------

bind = os.getenv("GUNICORN_BIND", "0.0.0.0:8000")

# Backlog: maximum number of pending connections. The default (2048) is
# fine for most deployments. Raise it only if you see connection-refused
# errors under heavy load.
backlog = int(os.getenv("GUNICORN_BACKLOG", "2048"))


# ---------------------------------------------------------------------------
# Worker processes
# ---------------------------------------------------------------------------

# The classic formula: 2 * CPU cores + 1 gives a good starting point for
# sync workers. For async workers (gevent, uvicorn) you can go higher
# because each worker handles many concurrent connections.
#
# Override via GUNICORN_WORKERS for container environments where CPU
# detection may not reflect your cgroup limits.
workers = int(os.getenv("GUNICORN_WORKERS", str(2 * multiprocessing.cpu_count() + 1)))

# Worker class options:
#   "sync"                       -- default, one request per worker at a time
#   "gevent"                     -- greenlet-based async (pip install gevent)
#   "uvicorn.workers.UvicornWorker" -- ASGI support (pip install uvicorn)
#
# Choose sync for CPU-bound workloads (heavy ORM, image processing).
# Choose gevent when you have many slow I/O-bound requests (external APIs).
# Choose uvicorn when your project uses Django Channels or async views.
worker_class = os.getenv("GUNICORN_WORKER_CLASS", "sync")

# Threads per worker. Only meaningful with the "gthread" worker class.
# With sync workers this is ignored.
threads = int(os.getenv("GUNICORN_THREADS", "1"))


# ---------------------------------------------------------------------------
# Timeouts
# ---------------------------------------------------------------------------

# How long a worker can take to handle a single request before the master
# kills and restarts it. 30s is the default; raise it if you have
# legitimate long-running views (report generation, large exports).
timeout = int(os.getenv("GUNICORN_TIMEOUT", "30"))

# Time to finish serving requests after receiving a restart signal.
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))

# Seconds to wait for requests on a keep-alive connection.
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))


# ---------------------------------------------------------------------------
# Memory leak prevention
# ---------------------------------------------------------------------------

# Restart a worker after it has handled this many requests. This is a
# simple defense against memory leaks in application code or C extensions.
# The jitter prevents all workers from restarting at the same time.
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", "1200"))
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", "200"))


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

# "-" means stdout/stderr, which is what you want in Docker / systemd.
accesslog = os.getenv("GUNICORN_ACCESS_LOG", "-")
errorlog = os.getenv("GUNICORN_ERROR_LOG", "-")

# Log level: debug, info, warning, error, critical
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")

# Use a structured access log format that pairs well with log aggregators.
# %({x-request-id}i)s captures a trace ID header set by your load balancer.
access_log_format = (
    '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s '
    '"%(f)s" "%(a)s" %(D)s %({x-request-id}i)s'
)


# ---------------------------------------------------------------------------
# Process naming
# ---------------------------------------------------------------------------

proc_name = os.getenv("GUNICORN_PROC_NAME", "django-app")


# ---------------------------------------------------------------------------
# Server hooks
# ---------------------------------------------------------------------------

def on_starting(server):
    """Called just before the master process is initialized."""
    pass


def pre_fork(server, worker):
    """Called just before a worker is forked.

    Close database connections in the master process so each forked
    worker gets its own connection. Without this, workers can share a
    connection and corrupt each other's state.
    """
    from django.db import connections

    for conn in connections.all():
        conn.close()


def post_fork(server, worker):
    """Called just after a worker has been forked.

    Good place to re-seed random number generators or set up
    worker-specific resources.
    """
    import random

    random.seed()

    server.log.info("Worker spawned (pid: %s)", worker.pid)


def pre_exec(server):
    """Called just before a new master process is forked (during upgrade)."""
    server.log.info("Forked child, re-executing.")


def worker_exit(server, worker):
    """Called when a worker exits.

    Clean up database connections to avoid leaked connections when a
    worker is replaced due to max_requests or timeout.
    """
    from django.db import connections

    for conn in connections.all():
        conn.close()


# ---------------------------------------------------------------------------
# SSL (uncomment if terminating TLS at Gunicorn instead of Nginx)
# ---------------------------------------------------------------------------

# keyfile = "/etc/ssl/private/app.key"
# certfile = "/etc/ssl/certs/app.crt"


# ---------------------------------------------------------------------------
# Development overrides
# ---------------------------------------------------------------------------

# Reload workers when code changes. Never use in production.
reload = os.getenv("GUNICORN_RELOAD", "false").lower() == "true"
