#!/usr/bin/env bash
# Full plan run with video + JSON under artifacts/e2e-<timestamp>/ (.env for URL, intent, keys).
# WALK_RANKED (default 5): after ranking, visit first N ranked URLs (clearer .webm). WALK_RANKED=0 to skip.
set -euo pipefail
WALK_RANKED="${WALK_RANKED:-5}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

TS="$(date +%Y-%m-%d_%H-%M-%S)"
OUT="$ROOT/artifacts/e2e-$TS"
mkdir -p "$OUT"
echo "E2E artifacts -> $OUT"

if [[ -x "$ROOT/.venv/bin/trailhead-agent" ]]; then
  AGENT="$ROOT/.venv/bin/trailhead-agent"
else
  AGENT="trailhead-agent"
fi

if [ "$WALK_RANKED" -gt 0 ] 2>/dev/null; then
  "$AGENT" plan --json --artifacts-dir "$OUT" --walk-ranked "$WALK_RANKED"
else
  "$AGENT" plan --json --artifacts-dir "$OUT"
fi
echo "Open: $OUT (e2e-plan-latest.json + *.webm)"
