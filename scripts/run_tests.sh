#!/bin/bash
# One-command local test runner.
#
# Usage: scripts/run_tests.sh [unittest discover arguments...]
#   With no arguments it runs `discover -s tests -v`. Extra arguments are
#   forwarded to `python -B -m unittest discover -s tests`, for example
#   `scripts/run_tests.sh -k sidecar` or `scripts/run_tests.sh -p 'test_engine*.py'`.
#
# Temp-root contract:
#   * DICOM_TEST_TMPDIR, when already set to an existing directory, is used as
#     is and is never removed by this script.
#   * Otherwise a private directory is created under ${TMPDIR:-/tmp}, exported
#     as DICOM_TEST_TMPDIR, printed, and removed on exit. Only that directory
#     is ever removed.
# Other environment:
#   PYTHON                     interpreter (default: python3)
#   DICOM_TEST_SUITE_DIR       test directory (default: <repo>/tests)
#   DICOM_TEST_TIMEOUT_SCALE   multiplier for subprocess timeouts (default 1)
# Exit status is unittest's.
set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SUITE_DIR="${DICOM_TEST_SUITE_DIR:-$PROJECT_DIR/tests}"
PYTHON_BIN="${PYTHON:-python3}"

created_root=""
# shellcheck disable=SC2329  # invoked through the EXIT trap
cleanup() {
  if [[ -n "$created_root" && -d "$created_root" ]]; then
    rm -rf -- "$created_root"
  fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

if [[ -n "${DICOM_TEST_TMPDIR:-}" ]]; then
  if [[ ! -d "$DICOM_TEST_TMPDIR" ]]; then
    echo "DICOM_TEST_TMPDIR is set but is not an existing directory: $DICOM_TEST_TMPDIR" >&2
    exit 2
  fi
else
  created_root="$(mktemp -d "${TMPDIR:-/tmp}/dicom-tests.XXXXXX")" || exit 2
  export DICOM_TEST_TMPDIR="$created_root"
fi
export PYTHONDONTWRITEBYTECODE=1

echo "Test temp root: $DICOM_TEST_TMPDIR" >&2
if [[ $# -eq 0 ]]; then
  set -- -v
fi
cd "$PROJECT_DIR" || exit 2
"$PYTHON_BIN" -B -m unittest discover -s "$SUITE_DIR" "$@"
status=$?
exit "$status"
