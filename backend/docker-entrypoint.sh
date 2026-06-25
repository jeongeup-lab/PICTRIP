#!/usr/bin/env sh
# Container entrypoint: apply forward-only schema migrations, then exec the app.
# deploy.sh (CT112) assumes "alembic upgrade head runs on container start"; this
# is where that happens. Idempotent — a no-op when the schema is already current.
# If a migration fails the container exits non-zero, the smoke check fails, and
# deploy.sh rolls back to the previous image tag.
set -e

echo "[entrypoint] alembic upgrade head"
alembic upgrade head

echo "[entrypoint] migrations applied; starting: $*"
exec "$@"
