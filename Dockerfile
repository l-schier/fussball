FROM python:3.12-slim AS dependencies

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

FROM python:3.12-slim AS runtime

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app:/app/fussball" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN groupadd --system app && \
    useradd --system --gid app --home-dir /app app && \
    mkdir -p /app/data && \
    chown app:app /app/data

COPY --from=dependencies --chown=app:app /app/.venv /app/.venv
COPY --chown=app:app alembic.ini ./alembic.ini
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app fussball ./fussball
COPY --chown=app:app container-entrypoint.sh /usr/local/bin/container-entrypoint
RUN chmod 0555 /usr/local/bin/container-entrypoint

VOLUME ["/app/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/health', timeout=2)" || exit 1

USER app
ENTRYPOINT ["/usr/local/bin/container-entrypoint"]
