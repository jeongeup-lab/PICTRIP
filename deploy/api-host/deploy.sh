#!/usr/bin/env bash
# CT112 deploy — pulled image → migrate → smoke → rollback on failure.
# Invoked by .github/workflows/backend-deploy.yml on the self-hosted runner.
set -euo pipefail

cd "$(dirname "$0")"

# .deploy.env pins the image tag (the only file deploy.sh mutates; .env is immutable).
PREV_TAG="$(grep -E '^IMAGE_TAG=' .deploy.env | cut -d= -f2 || true)"
NEW_TAG="${1:-${GITHUB_SHA:-latest}}"

echo "deploy: ${PREV_TAG:-<none>} -> ${NEW_TAG}"
sed -i "s/^IMAGE_TAG=.*/IMAGE_TAG=${NEW_TAG}/" .deploy.env || echo "IMAGE_TAG=${NEW_TAG}" >> .deploy.env

docker compose --env-file .deploy.env pull api
# alembic upgrade head runs on container start (forward-only)
docker compose --env-file .deploy.env up -d

# smoke: local + public
if ! curl -fsS http://127.0.0.1:8000/health >/dev/null \
   || ! curl -fsS https://api.pictrip.org/health >/dev/null; then
  echo "smoke FAILED — rolling back to ${PREV_TAG}"
  if [ -n "${PREV_TAG}" ]; then
    sed -i "s/^IMAGE_TAG=.*/IMAGE_TAG=${PREV_TAG}/" .deploy.env
    docker compose --env-file .deploy.env up -d
  fi
  exit 1
fi
echo "deploy OK: ${NEW_TAG}"
