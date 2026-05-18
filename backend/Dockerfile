# Backend container — FastAPI + SQLAlchemy + WeasyPrint PDF rendering.
#
# Base: python:3.13-slim-bookworm (Debian 12, glibc 2.36+, small surface).
# System libs needed by WeasyPrint at runtime:
#   - libcairo2, libpango-1.0-0, libpangoft2-1.0-0  (vector + text layout)
#   - libgdk-pixbuf-2.0-0                            (raster image loading)
#   - shared-mime-info                               (MIME db that GTK consults)
#   - fonts-dejavu, fonts-liberation                 (sane defaults for Spanish output)
# Plus libpq-dev for psycopg2/asyncpg builds and gcc for any wheel that ships
# only source distributions.
FROM python:3.12-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        # WeasyPrint native dependencies
        libcairo2 \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libgdk-pixbuf-2.0-0 \
        shared-mime-info \
        fonts-dejavu \
        fonts-liberation \
        # build tooling for any wheel that needs compilation
        gcc \
        libpq-dev \
        # libmagic for python-magic
        libmagic1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (fewer cache invalidations) then code.
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install -r /app/backend/requirements.txt && \
    pip install pytest>=8.2 pytest-asyncio>=0.23 anyio pypdf>=4

# Source mounted as volume in dev; baked-in in prod.
COPY backend /app/backend

# Alembic migrations live under backend/alembic and run with backend/ as cwd.
WORKDIR /app/backend

EXPOSE 8000

# uvicorn runs from repo root so `backend.src.main:app` import resolves.
WORKDIR /app
CMD ["uvicorn", "backend.src.main:app", "--host", "0.0.0.0", "--port", "8000"]
