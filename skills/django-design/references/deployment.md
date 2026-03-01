# Django Deployment Reference

## Vercel Serverless Deployment

Django on Vercel works well for small-to-medium applications. The key constraint is the serverless execution model: each request is handled by a fresh function invocation, with cold starts and execution time limits.

```python
# vercel.json
{
    "builds": [
        {
            "src": "project_name/wsgi.py",
            "use": "@vercel/python"
        }
    ],
    "routes": [
        {
            "src": "/static/(.*)",
            "dest": "/static/$1"
        },
        {
            "src": "/(.*)",
            "dest": "project_name/wsgi.py"
        }
    ]
}
```

**Vercel-specific considerations:**
- Static files: Use WhiteNoise or serve from a CDN. Vercel's filesystem is ephemeral.
- Database: Use an external managed database (Neon Postgres, PlanetScale, Supabase). SQLite will not persist.
- File uploads: Must go to external storage (S3, Cloudflare R2). Local filesystem is ephemeral.
- Background tasks: Vercel functions have execution time limits. For long-running tasks, use Vercel Cron or an external queue.
- Cold starts: Keep dependencies lean. Heavy packages increase cold start time.

```python
# settings/production.py for Vercel

import dj_database_url

DATABASES = {
    'default': dj_database_url.config(
        default=env('DATABASE_URL'),
        conn_max_age=0,  # no persistent connections in serverless
    )
}

# WhiteNoise for static files
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    ...
]
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
```

## Traditional Deployment (Gunicorn + Nginx)

The classic deployment for Django applications with full control.

```bash
# Install production dependencies
pip install gunicorn psycopg2-binary

# gunicorn.conf.py
import multiprocessing

bind = "0.0.0.0:8000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "gthread"
threads = 4
timeout = 120
keepalive = 5
errorlog = "-"
accesslog = "-"
loglevel = "info"
```

```nginx
# nginx.conf
server {
    listen 80;
    server_name yourdomain.org;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl;
    server_name yourdomain.org;

    ssl_certificate /etc/letsencrypt/live/yourdomain.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.org/privkey.pem;

    # Static files served directly by Nginx
    location /static/ {
        alias /path/to/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Media files
    location /media/ {
        alias /path/to/media/;
        expires 7d;
    }

    # Proxy to Gunicorn
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    client_max_body_size 20M;
}
```

## Docker Configuration

```dockerfile
# Dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements/production.txt requirements.txt
RUN pip install -r requirements.txt

# Copy application
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

# Run with Gunicorn
EXPOSE 8000
CMD ["gunicorn", "project_name.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "4", \
     "--threads", "2"]
```

```yaml
# docker-compose.yml (for development)
services:
  web:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - .:/app
    environment:
      - DJANGO_SETTINGS_MODULE=project_name.settings.development
      - DATABASE_URL=postgres://postgres:postgres@db:5432/app_db
    depends_on:
      - db
      - redis
    command: python manage.py runserver 0.0.0.0:8000

  db:
    image: postgres:16
    environment:
      POSTGRES_DB: app_db
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  postgres_data:
```

## Environment Variable Management

```python
# settings/base.py
import environ

env = environ.Env()

# Read .env file in development
if env.bool('READ_DOT_ENV', default=False):
    environ.Env.read_env(BASE_DIR / '.env')

SECRET_KEY = env('DJANGO_SECRET_KEY')
DEBUG = env.bool('DEBUG', default=False)
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=[])

DATABASES = {
    'default': env.db('DATABASE_URL'),
}
```

```bash
# .env.example (commit this, not .env)
DJANGO_SECRET_KEY=change-me-to-a-real-secret-key
DEBUG=True
READ_DOT_ENV=True
DATABASE_URL=postgres://postgres:postgres@localhost:5432/app_db
ALLOWED_HOSTS=localhost,127.0.0.1
```

**Never commit `.env` files.** Add `.env` to `.gitignore`. Commit a `.env.example` with placeholder values so new developers know what to configure.

## Database Connection Pooling

Serverless environments create a new connection per request. Without pooling, this overwhelms the database.

```python
# Option 1: PgBouncer (external pooler, recommended for production)
# Configure PgBouncer on your server or use a managed service
# Then point Django at PgBouncer instead of directly at Postgres
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'HOST': 'pgbouncer-host',
        'PORT': 6432,  # PgBouncer port
        'NAME': 'app_db',
        'CONN_MAX_AGE': 0,  # let PgBouncer handle connection reuse
    }
}

# Option 2: Neon with connection pooling enabled
# Neon provides a pooled connection string
DATABASES = {
    'default': dj_database_url.config(
        default=env('DATABASE_URL'),  # use the pooled endpoint
        conn_max_age=0,
    )
}

# Option 3: django-db-connection-pool (in-process pooling)
# Good for traditional deployments without external pooler
DATABASES = {
    'default': {
        'ENGINE': 'dj_db_conn_pool.backends.postgresql',
        'POOL_OPTIONS': {
            'POOL_SIZE': 10,
            'MAX_OVERFLOW': 5,
        },
        ...
    }
}
```

## Static File Handling

```python
# Development: Django serves static files directly
# (automatic when DEBUG=True)

# Production Option 1: WhiteNoise (simplest)
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # right after SecurityMiddleware
    ...
]
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# Production Option 2: S3 + CloudFront
STORAGES = {
    "staticfiles": {
        "BACKEND": "storages.backends.s3boto3.S3StaticStorage",
    },
}
AWS_STORAGE_BUCKET_NAME = env('AWS_STATIC_BUCKET')
AWS_S3_CUSTOM_DOMAIN = env('CDN_DOMAIN')
STATIC_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/static/'
```

## Health Checks

```python
# apps/core/views.py
from django.http import JsonResponse
from django.db import connection


def health_check(request):
    """Basic health check for load balancers and monitoring."""
    health = {'status': 'ok'}

    # Check database
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        health['database'] = 'ok'
    except Exception:
        health['database'] = 'error'
        health['status'] = 'degraded'

    status_code = 200 if health['status'] == 'ok' else 503
    return JsonResponse(health, status=status_code)


# urls.py
urlpatterns = [
    path('health/', health_check, name='health-check'),
    ...
]
```

## Migration Strategies

```bash
# Before deploying: check for migration issues
python manage.py showmigrations
python manage.py migrate --plan

# For zero-downtime deployments, migrations must be backwards-compatible:
# 1. Add new columns as nullable (null=True) first
# 2. Deploy code that writes to both old and new columns
# 3. Backfill the new column
# 4. Deploy code that reads from the new column
# 5. Remove the old column in a separate migration

# For large tables, use RunSQL for data migrations instead of Python
# (Python data migrations load all rows into memory)
```

```python
# migrations/0005_backfill_word_count.py
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('content', '0004_add_word_count'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                UPDATE content_essay
                SET word_count = array_length(
                    regexp_split_to_array(trim(body), '\\s+'), 1
                )
                WHERE word_count IS NULL
                AND body IS NOT NULL
                AND body != ''
            """,
            reverse_sql="""
                UPDATE content_essay
                SET word_count = NULL
            """,
        ),
    ]
```

## Logging Configuration

```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'WARNING',  # reduce Django's default noise
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
        'apps': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
```
