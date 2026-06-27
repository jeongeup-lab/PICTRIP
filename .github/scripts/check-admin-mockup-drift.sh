#!/usr/bin/env bash
# Admin UI drift check: the served copy (backend/app/modules/admin/static/) MUST be
# byte-identical to the UI SSOT (admin/mockups/) for every served file.
# Invariant: CLAUDE.md "admin static/ is a copy of admin/mockups/ (UI SSOT)".
# history/ (mockup-only version archive) and static/README.md (SSOT pointer) are
# intentionally not part of the served set and are skipped.
set -euo pipefail

SSOT="admin/mockups"
COPY="backend/app/modules/admin/static"

if [ ! -d "$SSOT" ] || [ ! -d "$COPY" ]; then
  echo "ERROR: expected dirs missing ($SSOT and/or $COPY)" >&2
  exit 2
fi

fail=0
# Served files = everything tracked under static/ except README.md.
while IFS= read -r f; do
  rel="${f#"$COPY"/}"
  [ "$rel" = "README.md" ] && continue
  if [ ! -f "$SSOT/$rel" ]; then
    echo "DRIFT: $f has no SSOT counterpart at $SSOT/$rel"
    fail=1
    continue
  fi
  if ! cmp -s "$f" "$SSOT/$rel"; then
    echo "DRIFT: $f differs from SSOT $SSOT/$rel"
    fail=1
  fi
done < <(find "$COPY" -type f)

if [ "$fail" -ne 0 ]; then
  echo ""
  echo "Admin static/ has drifted from admin/mockups/ (UI SSOT)."
  echo "Re-copy the served files from admin/mockups/ into $COPY/ and commit."
  exit 1
fi

echo "OK: admin static/ matches admin/mockups/ (all served files byte-identical)."
