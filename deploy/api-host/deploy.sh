#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

PREV_TAG="$(grep -E '^IMAGE_TAG=' .deploy.env | cut -d= -f2 || true)"
NEW_TAG="${1:-${GITHUB_SHA:-latest}}"

echo "deploy: ${PREV_TAG:-<none>} -> ${NEW_TAG}"
sed -i "s/^IMAGE_TAG=.*/IMAGE_TAG=${NEW_TAG}/" .deploy.env || echo "IMAGE_TAG=${NEW_TAG}" >> .deploy.env

docker compose --env-file .deploy.env pull api

for _cid in $(docker ps --filter "publish=8000" -q); do
  _name="$(docker inspect -f '{{.Name}}' "$_cid" | sed 's#^/##')"
  case "$_name" in
    api-host[-_]api[-_]*) ;;
    *) echo "freeing :8000 held by foreign container ${_name} (${_cid})"
       docker rm -f "$_cid" >/dev/null ;;
  esac
done
if ! docker ps --filter "publish=8000" -q | grep -q . \
   && ss -ltn 'sport = :8000' 2>/dev/null | grep -q LISTEN; then
  echo "ERROR: :8000 is held by a non-docker host process. Free it once on CT112:"
  echo "  sudo ss -ltnp 'sport = :8000'"
  echo "  sudo systemctl stop <old-api-unit>"
  exit 1
fi

docker compose --env-file .deploy.env up -d

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

IMAGE_REPO="ghcr.io/jeongeup-lab/pictrip-backend"
docker images "${IMAGE_REPO}" --format '{{.Tag}}' | while read -r _tag; do
  case "${_tag}" in
    "${NEW_TAG}"|"${PREV_TAG}") ;;
    *) echo "gc: removing stale image ${IMAGE_REPO}:${_tag}"
       docker rmi "${IMAGE_REPO}:${_tag}" >/dev/null 2>&1 || true ;;
  esac
done
docker image prune -f >/dev/null 2>&1 || true
