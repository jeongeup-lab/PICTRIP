#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

DEPLOY_ENV="${DEPLOY_ENV:-.deploy.env}"
mkdir -p "$(dirname "${DEPLOY_ENV}")"
if [ ! -f "${DEPLOY_ENV}" ]; then
  cp .deploy.env.example "${DEPLOY_ENV}"
fi

ENV_IMAGE="$(grep -E '^IMAGE=' "${DEPLOY_ENV}" | cut -d= -f2- | tr -d '\r' || true)"
if [ -z "${ENV_IMAGE}" ]; then
  echo "ERROR: IMAGE is missing from ${DEPLOY_ENV}"
  exit 1
fi
if [ -n "${IMAGE:-}" ] && [ "${IMAGE}" != "${ENV_IMAGE}" ]; then
  echo "ERROR: IMAGE differs between the shell and ${DEPLOY_ENV}"
  exit 1
fi
IMAGE_REPO="${IMAGE:-${ENV_IMAGE}}"
export IMAGE="${IMAGE_REPO}"

STATE_TAG="$(grep -E '^IMAGE_TAG=' "${DEPLOY_ENV}" | cut -d= -f2- | tr -d '\r' || true)"
STATE_REVISION="$(grep -E '^DB_REVISION=' "${DEPLOY_ENV}" | cut -d= -f2- | tr -d '\r' || true)"
NEW_TAG="${1:-${GITHUB_SHA:-latest}}"
if ! printf '%s\n' "${NEW_TAG}" | grep -Eq '^[0-9a-f]{40}$'; then
  echo "ERROR: deploy tag must be a full immutable git SHA: ${NEW_TAG}"
  exit 1
fi

valid_tag() {
  printf '%s\n' "$1" | grep -Eq '^[0-9a-f]{40}$'
}

valid_revision() {
  printf '%s\n' "$1" | grep -Eq '^[0-9]{4}_[[:alnum:]_]+$'
}

find_running_api() {
  docker ps \
    --filter 'label=com.docker.compose.project=api-host' \
    --filter 'label=com.docker.compose.service=api' \
    --filter 'label=com.docker.compose.oneoff=False' \
    --filter 'publish=8000' \
    -q | sed -n '1p'
}

compose_with_tag() {
  local _tag="$1"
  shift
  IMAGE="${IMAGE_REPO}" IMAGE_TAG="${_tag}" \
    docker compose --env-file "${DEPLOY_ENV}" "$@"
}

record_success() {
  local _tag="$1"
  local _revision="$2"
  local _state_tmp="${DEPLOY_ENV}.tmp.$$"
  (
    umask 077
    printf 'IMAGE=%s\nIMAGE_TAG=%s\nDB_REVISION=%s\n' \
      "${IMAGE_REPO}" "${_tag}" "${_revision}" > "${_state_tmp}"
  )
  mv "${_state_tmp}" "${DEPLOY_ENV}"
}

PREV_TAG=""
PREV_REVISION=""

_api_cid="$(find_running_api)"
if [ -n "${_api_cid}" ]; then
  if curl -fsS --max-time 5 http://127.0.0.1:8000/health >/dev/null 2>&1; then
    _previous_image="$(docker inspect -f '{{.Config.Image}}' "${_api_cid}")"
    case "${_previous_image}" in
      "${IMAGE_REPO}:"*) _container_tag="${_previous_image#"${IMAGE_REPO}:"}" ;;
      *)
        echo "ERROR: previous api image does not belong to ${IMAGE_REPO}: ${_previous_image}"
        exit 1
        ;;
    esac
    _container_revision=""
    if ! _container_revision="$(
      docker exec "${_api_cid}" alembic current 2>/dev/null |
        awk 'NF { print $1; exit }'
    )"; then
      _container_revision=""
    fi
    if ! valid_tag "${_container_tag}" || ! valid_revision "${_container_revision}"; then
      echo "ERROR: running api does not expose an immutable image tag and database revision"
      exit 1
    fi
    PREV_TAG="${_container_tag}"
    PREV_REVISION="${_container_revision}"
  else
    echo "WARNING: running api failed its local health check; using durable deploy state"
  fi
fi

if [ -z "${PREV_TAG}" ]; then
  if valid_tag "${STATE_TAG}" && valid_revision "${STATE_REVISION}"; then
    PREV_TAG="${STATE_TAG}"
    PREV_REVISION="${STATE_REVISION}"
  elif [ "${ALLOW_INITIAL_DEPLOY:-0}" != 1 ]; then
    echo "ERROR: no healthy api or durable last-success state is available"
    echo "Set ALLOW_INITIAL_DEPLOY=1 only for a verified first deployment."
    exit 1
  fi
fi

echo "deploy: ${PREV_TAG:-<none>} -> ${NEW_TAG}"
compose_with_tag "${NEW_TAG}" pull api

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

wait_local() {
  for _ in $(seq 1 30); do
    if curl -fsS --max-time 5 http://127.0.0.1:8000/health >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  return 1
}

restart_new() {
  compose_with_tag "${NEW_TAG}" up -d || true
}

rollback_failed_deploy() {
  if [ -z "${PREV_TAG}" ]; then
    echo "no previous image is available; stopping the failed deployment"
    compose_with_tag "${NEW_TAG}" stop api || true
    return
  fi

  if compose_with_tag "${NEW_TAG}" stop api \
     && compose_with_tag "${NEW_TAG}" run --rm --no-deps \
          --entrypoint alembic api downgrade "${PREV_REVISION}"; then
    if compose_with_tag "${PREV_TAG}" up -d && wait_local; then
      record_success "${PREV_TAG}" "${PREV_REVISION}"
      echo "rollback OK: ${PREV_TAG} at database revision ${PREV_REVISION}"
    else
      echo "rollback image failed health check; restarting ${NEW_TAG}"
      restart_new
    fi
  else
    echo "database downgrade or api stop failed; restarting ${NEW_TAG} instead of an incompatible old image"
    restart_new
  fi
}

smoke_ok() {
  curl -fsS --max-time 5 http://127.0.0.1:8000/health >/dev/null 2>&1 &&
    curl -fsS --max-time 5 https://api.pictrip.org/health >/dev/null 2>&1
}

if ! compose_with_tag "${NEW_TAG}" up -d; then
  echo "ERROR: api container failed to start"
  rollback_failed_deploy
  exit 1
fi

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
  rollback_failed_deploy
  exit 1
fi

_new_api_cid="$(find_running_api)"
NEW_REVISION=""
if [ -n "${_new_api_cid}" ]; then
  if ! NEW_REVISION="$(
    docker exec "${_new_api_cid}" alembic current 2>/dev/null |
      awk 'NF { print $1; exit }'
  )"; then
    NEW_REVISION=""
  fi
fi
if ! valid_revision "${NEW_REVISION}"; then
  echo "ERROR: deployed database revision could not be recorded"
  rollback_failed_deploy
  exit 1
fi
record_success "${NEW_TAG}" "${NEW_REVISION}"
echo "deploy OK: ${NEW_TAG}"

echo "warming channel caches"
if ! compose_with_tag "${NEW_TAG}" exec -T api \
     timeout "${WARM_TIMEOUT_SECONDS:-120}" python -m scripts.warm_channels; then
  echo "channel warm skipped (non-fatal)"
fi

docker images "${IMAGE_REPO}" --format '{{.Tag}}' | while read -r _tag; do
  case "${_tag}" in
    "${NEW_TAG}"|"${PREV_TAG}") ;;
    *) echo "gc: removing stale image ${IMAGE_REPO}:${_tag}"
       docker rmi "${IMAGE_REPO}:${_tag}" >/dev/null 2>&1 || true ;;
  esac
done
docker image prune -f >/dev/null 2>&1 || true
