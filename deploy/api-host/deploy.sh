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

# Free :8000 before compose rebinds it. A leftover/foreign container squatting the
# public API port makes `up` fail with "port is already allocated" (the one-time
# CT112 cutover). Our own compose api container is left for `up` to recreate; only
# foreign containers are removed. A non-docker host process holding :8000 can't be
# safely killed here, so fail fast with guidance instead of a cryptic docker error.
for _cid in $(docker ps --filter "publish=8000" -q); do
  _name="$(docker inspect -f '{{.Name}}' "$_cid" | sed 's#^/##')"
  case "$_name" in
    api-host[-_]api[-_]*) ;;  # ours — compose recreates it
    *) echo "freeing :8000 held by foreign container ${_name} (${_cid})"
       docker rm -f "$_cid" >/dev/null ;;
  esac
done
if ! docker ps --filter "publish=8000" -q | grep -q . \
   && ss -ltn 'sport = :8000' 2>/dev/null | grep -q LISTEN; then
  echo "ERROR: :8000 is held by a non-docker host process. Free it once on CT112:"
  echo "  sudo ss -ltnp 'sport = :8000'        # find the PID/unit"
  echo "  sudo systemctl stop <old-api-unit>   # or: sudo kill <pid>"
  exit 1
fi

# alembic upgrade head runs on container start (forward-only)
docker compose --env-file .deploy.env up -d

# smoke: poll local + public health until the new container finishes booting
# (alembic upgrade + uvicorn start), up to ~60s, before declaring failure — a
# single immediate check races the container startup and false-fails.
smoke_ok() {
  curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1 &&
    curl -fsS https://api.pictrip.org/health >/dev/null 2>&1
}
_ok=0
for _ in $(seq 1 30); do
  if smoke_ok; then
    _ok=1
    break
  fi
  sleep 2
done
if [ "${_ok}" -ne 1 ]; then
  echo "smoke FAILED after ~60s — rolling back to ${PREV_TAG:-<none>}"
  if [ -n "${PREV_TAG}" ]; then
    sed -i "s/^IMAGE_TAG=.*/IMAGE_TAG=${PREV_TAG}/" .deploy.env
    docker compose --env-file .deploy.env up -d
  fi
  exit 1
fi
echo "deploy OK: ${NEW_TAG}"
