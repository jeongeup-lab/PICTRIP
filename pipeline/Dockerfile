# pictrip-data ETL — CT111
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml ./
RUN uv sync --no-dev --no-install-project
COPY . .
RUN uv sync --no-dev

# default: daily sync (cron/systemd timer invokes this on CT111)
ENTRYPOINT ["uv", "run", "pictrip-data"]
CMD ["sync-daily"]
