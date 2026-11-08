#!/usr/bin/env bash
# Run the unit tests (and the UI smoke test with --smoke). Stops at the first failure.
# Usage: scripts/test.sh [--smoke]
# Uses .venv/bin/python when it exists, plain python otherwise (CI and the cloud have no venv).
set -u
cd "$(dirname "$0")/.."
PY=python
[ -x .venv/bin/python ] && PY=.venv/bin/python
for t in tests/test_*.py; do
  echo "== $t"
  "$PY" "$t" || { echo "FAILED: $t"; exit 1; }
done
if [ "${1:-}" = "--smoke" ]; then
  if [ ! -f congress.db ]; then echo "congress.db missing: smoke test not run"; exit 2; fi
  echo "== tests/ui_smoke.py"
  "$PY" tests/ui_smoke.py || { echo "FAILED: tests/ui_smoke.py"; exit 1; }
fi
echo "OK"
