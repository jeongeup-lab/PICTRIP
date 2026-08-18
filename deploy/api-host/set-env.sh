#!/usr/bin/env bash
# CT112 의 /opt/pictrip-api/.env 를 제자리에서 갱신한다.
#
# 왜 제자리여야 하나: 이 파일은 api 컨테이너에 /app/.env 로 bind mount 되어 있다.
# 파일 bind mount 는 경로가 아니라 inode 를 붙잡는다. `sed -i` 나 `mv` 는 새 inode 를
# 만들고 이름만 바꿔치기하므로, 컨테이너는 갱신 전 파일을 계속 보게 된다.
# 그 상태에서 배포가 돌면 `docker exec api alembic current` 가 옛 설정으로 죽고,
# deploy.sh 의 "immutable image tag and database revision" 가드가 실패한다.
#
# 사용:
#   ssh root@<pve> 'pct exec 112 -- bash -s' < deploy/api-host/set-env.sh KEY VALUE
#   ssh root@<pve> 'pct exec 112 -- bash -s -- --unset KEY' < deploy/api-host/set-env.sh
set -euo pipefail

ENV_FILE="${PICTRIP_ENV_FILE:-/opt/pictrip-api/.env}"

usage() {
  echo "usage: set-env.sh KEY VALUE | set-env.sh --unset KEY" >&2
  exit 2
}

[ -f "${ENV_FILE}" ] || { echo "ERROR: ${ENV_FILE} not found" >&2; exit 1; }
[ $# -ge 1 ] || usage

if [ "${1}" = "--unset" ]; then
  [ $# -eq 2 ] || usage
  key="${2}"
  value=""
  unset_only=1
else
  [ $# -eq 2 ] || usage
  key="${1}"
  value="${2}"
  unset_only=0
fi

case "${key}" in
  [A-Z_]*[A-Z0-9_]) ;;
  *) echo "ERROR: key must be upper snake case: ${key}" >&2; exit 1 ;;
esac

before_inode="$(stat -c %i "${ENV_FILE}")"
cp -f "${ENV_FILE}" "${ENV_FILE}.bak.$(date +%s)"

tmp="$(mktemp)"
trap 'rm -f "${tmp}"' EXIT
grep -v -E "^${key}=" "${ENV_FILE}" > "${tmp}" || true
if [ "${unset_only}" -eq 0 ]; then
  printf '%s=%s\n' "${key}" "${value}" >> "${tmp}"
fi

# 제자리 truncate + write — inode 를 유지해 bind mount 가 그대로 따라온다.
cat "${tmp}" > "${ENV_FILE}"

after_inode="$(stat -c %i "${ENV_FILE}")"
if [ "${before_inode}" != "${after_inode}" ]; then
  echo "ERROR: inode changed (${before_inode} -> ${after_inode}); bind mount is now stale" >&2
  exit 1
fi

echo "ok: ${key} $([ "${unset_only}" -eq 1 ] && echo removed || echo set) · inode ${after_inode} preserved"
