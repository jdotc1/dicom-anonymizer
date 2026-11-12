#!/bin/bash
# Non-gating lint baseline. Runs whichever of ruff, mypy, shellcheck and
# actionlint are installed and prints per-tool finding counts. Nothing is
# installed and nothing is gated: the exit status is 0 unless --strict is
# given, in which case it is 1 when any tool reports findings.
# Usage: scripts/lint.sh [--strict]
set -uo pipefail

strict=0
case "${1:-}" in
  '') ;;
  --strict) strict=1 ;;
  *) echo "usage: scripts/lint.sh [--strict]" >&2; exit 2 ;;
esac

cd "$(dirname "$0")/.." || exit 2
total=0

report() {  # name count
  printf '%-12s %s\n' "$1" "$2"
  if [[ "$2" =~ ^[0-9]+$ ]]; then total=$((total + $2)); fi
}

if command -v ruff >/dev/null 2>&1; then
  count="$(ruff check --output-format concise --no-cache 2>/dev/null | grep -c -E '^[^ ]+:[0-9]+:[0-9]+: ')"
  report ruff "$count"
else
  report ruff "not installed"
fi

if command -v mypy >/dev/null 2>&1; then
  count="$(mypy --cache-dir=/dev/null engine 2>/dev/null | grep -c ': error:')"
  report mypy "$count"
else
  report mypy "not installed"
fi

if command -v shellcheck >/dev/null 2>&1; then
  count="$(shellcheck -f gcc ./*.sh scripts/*.sh 2>/dev/null | grep -c ': ')"
  report shellcheck "$count"
else
  report shellcheck "not installed"
fi

if command -v actionlint >/dev/null 2>&1; then
  count="$(actionlint -oneline .github/workflows/*.yml 2>/dev/null | grep -c ': ')"
  report actionlint "$count"
else
  report actionlint "not installed"
fi

printf '%-12s %s\n' total "$total"
if [[ $strict -eq 1 && $total -gt 0 ]]; then exit 1; fi
exit 0
