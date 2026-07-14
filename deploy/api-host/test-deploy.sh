#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DEPLOY_SCRIPT="${ROOT}/deploy/api-host/deploy.sh"
IMAGE_REPO="ghcr.io/jeongeup-lab/pictrip-backend"
OLD_TAG="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
NEW_TAG="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
OLD_REVISION="0018_previous"
NEW_REVISION="0019_current"
TEST_ROOT="$(mktemp -d)"
MOCK_BIN="${TEST_ROOT}/bin"
mkdir -p "${MOCK_BIN}"

cleanup() {
  if [ "${KEEP_TEST_ROOT:-0}" = "1" ]; then
    printf 'test artifacts: %s\n' "${TEST_ROOT}" >&2
  else
    rm -rf "${TEST_ROOT}"
  fi
}

trap cleanup EXIT

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

assert_eq() {
  _expected="$1"
  _actual="$2"
  _message="$3"
  if [ "${_actual}" != "${_expected}" ]; then
    printf 'expected:\n%s\nactual:\n%s\n' "${_expected}" "${_actual}" >&2
    fail "${_message}"
  fi
}

assert_contains() {
  _needle="$1"
  _file="$2"
  _message="$3"
  grep -F -- "${_needle}" "${_file}" >/dev/null || fail "${_message}"
}

assert_not_contains() {
  _needle="$1"
  _file="$2"
  _message="$3"
  if grep -F -- "${_needle}" "${_file}" >/dev/null; then
    fail "${_message}"
  fi
}

cat > "${MOCK_BIN}/docker" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'docker\tIMAGE_TAG=%s\t%s\n' "${IMAGE_TAG:-}" "$*" >> "${MOCK_CALLS}"

if [ "${1:-}" = "ps" ]; then
  case "${MOCK_MODE}" in
    recover)
      if [ -f "${MOCK_STATE}/new-up" ]; then
        printf 'new-api\n'
      else
        printf 'old-api\n'
      fi
      ;;
    rollback) ;;
    untrusted)
      if printf '%s\n' "$*" | grep -Eq '(^| )(-a|--all)( |$)'; then
        printf 'stopped-api\n'
      elif ! printf '%s\n' "$*" | grep -F 'label=com.docker.compose.oneoff=False' >/dev/null; then
        printf 'oneoff-api\n'
      fi
      ;;
  esac
  exit 0
fi

if [ "${1:-}" = "inspect" ]; then
  if [ "${3:-}" = "{{.Config.Image}}" ] && [ "${4:-}" = "old-api" ]; then
    printf '%s:%s\n' "${IMAGE_REPO}" "${OLD_TAG}"
    exit 0
  fi
  if [ "${3:-}" = "{{.Name}}" ]; then
    printf '/api-host-api-1\n'
    exit 0
  fi
  exit 1
fi

if [ "${1:-}" = "exec" ]; then
  case "${2:-}" in
    old-api) printf '%s (head)\n' "${OLD_REVISION}" ;;
    new-api) printf '%s (head)\n' "${MOCK_NEW_REVISION}" ;;
    *) exit 1 ;;
  esac
  exit 0
fi

if [ "${1:-}" = "compose" ]; then
  case " $* " in
    *" pull api "*) exit 0 ;;
    *" stop api "*) exit 0 ;;
    *" run --rm --no-deps --entrypoint alembic api downgrade ${OLD_REVISION} "*)
      touch "${MOCK_STATE}/downgraded"
      exit 0
      ;;
    *" up -d "*)
      if [ "${MOCK_MODE}" = "rollback" ] && [ "${IMAGE_TAG}" = "${NEW_TAG}" ]; then
        touch "${MOCK_STATE}/new-up-failed"
        exit 1
      fi
      if [ "${IMAGE_TAG}" = "${NEW_TAG}" ]; then
        touch "${MOCK_STATE}/new-up"
      fi
      if [ "${IMAGE_TAG}" = "${OLD_TAG}" ]; then
        touch "${MOCK_STATE}/old-up"
      fi
      exit 0
      ;;
  esac
  exit 0
fi

if [ "${1:-}" = "images" ] || [ "${1:-}" = "image" ] || [ "${1:-}" = "rmi" ]; then
  exit 0
fi

exit 1
EOF

cat > "${MOCK_BIN}/curl" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'curl\t%s\n' "$*" >> "${MOCK_CALLS}"
case "${MOCK_MODE}" in
  recover) exit 0 ;;
  rollback)
    [ -f "${MOCK_STATE}/old-up" ]
    exit $?
    ;;
  untrusted) exit 1 ;;
esac
EOF

cat > "${MOCK_BIN}/ss" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF

cat > "${MOCK_BIN}/sleep" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF

chmod +x "${MOCK_BIN}/docker" "${MOCK_BIN}/curl" "${MOCK_BIN}/ss" "${MOCK_BIN}/sleep"

run_deploy() {
  _case_dir="$1"
  _mode="$2"
  set +e
  PATH="${MOCK_BIN}:${PATH}" \
    DEPLOY_ENV="${_case_dir}/deploy.env" \
    MOCK_MODE="${_mode}" \
    MOCK_STATE="${_case_dir}/mock-state" \
    MOCK_CALLS="${_case_dir}/calls.log" \
    IMAGE_REPO="${IMAGE_REPO}" \
    OLD_TAG="${OLD_TAG}" \
    NEW_TAG="${NEW_TAG}" \
    OLD_REVISION="${OLD_REVISION}" \
    MOCK_NEW_REVISION="${NEW_REVISION}" \
    "${DEPLOY_SCRIPT}" "${NEW_TAG}" > "${_case_dir}/output.log" 2>&1
  RUN_STATUS=$?
  set -e
}

expected_state() {
  printf 'IMAGE=%s\nIMAGE_TAG=%s\nDB_REVISION=%s' "${IMAGE_REPO}" "$1" "$2"
}

test_missing_state_recovers_running_service() {
  _case_dir="${TEST_ROOT}/recover"
  mkdir -p "${_case_dir}/mock-state"
  : > "${_case_dir}/calls.log"

  run_deploy "${_case_dir}" recover

  assert_eq "0" "${RUN_STATUS}" "healthy deployment should succeed"
  assert_eq "$(expected_state "${NEW_TAG}" "${NEW_REVISION}")" "$(cat "${_case_dir}/deploy.env")" "successful deployment should atomically record the new state"
  assert_contains "deploy: ${OLD_TAG} -> ${NEW_TAG}" "${_case_dir}/output.log" "running immutable tag should be recovered"
  assert_contains $'docker\tIMAGE_TAG=\tinspect -f {{.Config.Image}} old-api' "${_case_dir}/calls.log" "running image should be inspected"
  assert_contains $'docker\tIMAGE_TAG=\texec old-api alembic current' "${_case_dir}/calls.log" "running revision should be inspected"
  assert_contains $'docker\tIMAGE_TAG='"${NEW_TAG}"$'\tcompose --env-file ' "${_case_dir}/calls.log" "new image should be started with its immutable tag"
}

test_initial_up_failure_rolls_back_durable_state() {
  _case_dir="${TEST_ROOT}/rollback"
  mkdir -p "${_case_dir}/mock-state"
  : > "${_case_dir}/calls.log"
  expected_state "${OLD_TAG}" "${OLD_REVISION}" > "${_case_dir}/deploy.env"
  printf '\n' >> "${_case_dir}/deploy.env"

  run_deploy "${_case_dir}" rollback

  assert_eq "1" "${RUN_STATUS}" "failed initial up should fail the deployment"
  assert_eq "$(expected_state "${OLD_TAG}" "${OLD_REVISION}")" "$(cat "${_case_dir}/deploy.env")" "rollback should retain the durable last-success state"
  assert_contains "rollback OK: ${OLD_TAG} at database revision ${OLD_REVISION}" "${_case_dir}/output.log" "rollback should restore the previous image and revision"
  [ -f "${_case_dir}/mock-state/downgraded" ] || fail "rollback should downgrade the database"
  [ -f "${_case_dir}/mock-state/old-up" ] || fail "rollback should start the previous image"
}

test_stopped_and_oneoff_containers_are_not_trusted() {
  _case_dir="${TEST_ROOT}/untrusted"
  mkdir -p "${_case_dir}/mock-state"
  : > "${_case_dir}/calls.log"

  run_deploy "${_case_dir}" untrusted

  assert_eq "1" "${RUN_STATUS}" "missing trusted state should fail closed"
  assert_contains "ERROR: no healthy api or durable last-success state is available" "${_case_dir}/output.log" "untrusted containers should not provide rollback state"
  assert_contains "label=com.docker.compose.oneoff=False" "${_case_dir}/calls.log" "running lookup should exclude one-off containers"
  assert_contains "publish=8000" "${_case_dir}/calls.log" "running lookup should require the published API port"
  assert_not_contains $'docker\tIMAGE_TAG=\tps -a' "${_case_dir}/calls.log" "running lookup should not include stopped containers"
  assert_not_contains $'docker\tIMAGE_TAG=\tinspect' "${_case_dir}/calls.log" "stopped or one-off containers should not be inspected"
  assert_not_contains $'docker\tIMAGE_TAG=\texec' "${_case_dir}/calls.log" "stopped or one-off containers should not supply a revision"
  assert_not_contains $'\tcompose ' "${_case_dir}/calls.log" "deployment should stop before mutating Docker state"
}

test_missing_state_recovers_running_service
test_initial_up_failure_rolls_back_durable_state
test_stopped_and_oneoff_containers_are_not_trusted
printf 'deploy.sh regression tests passed\n'
