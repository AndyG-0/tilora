# Build context is the repo root (not backend/) so this can also pick up the
# top-level VERSION file that app/update_check.py reads at import time — see
# docker-compose.yml's `build.context`.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --no-dev --no-install-project

COPY backend/app ./app
COPY backend/config ./config
COPY VERSION /VERSION

RUN uv sync --no-dev

# Runs as a fixed-UID non-root user rather than root, per container security
# best practice. /app/data is where DB_PATH/ICLOUD_SESSION_DIR point in
# docker-compose.yml — pre-creating it here (owned by the app user) means
# Docker copies that ownership into the named volume the first time it's
# mounted, instead of the volume defaulting to root:root and the app being
# unable to write to it.
RUN groupadd --gid 1000 tilora \
    && useradd --uid 1000 --gid tilora --home-dir /app --shell /usr/sbin/nologin tilora \
    && mkdir -p /app/data \
    && chown -R tilora:tilora /app

COPY backend/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

USER tilora

EXPOSE 8000

ENTRYPOINT ["docker-entrypoint.sh"]

# Binds all interfaces inside the container, not just localhost — required
# for Docker's port-publishing (`ports:` in compose) to reach the process at
# all, since a container's "localhost" isn't the host's. The actual exposure
# boundary is the `ports:` mapping in docker-compose.yml/.prod.yml (and
# CORS_ORIGIN for which browser origins may call it), not this bind address;
# there's no auth in front of it, so treat that mapping as the real
# perimeter — see README's "Network exposure" section.
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
