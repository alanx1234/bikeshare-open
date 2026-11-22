#!/usr/bin/env bash
# PostToolUse hook: re-run the full test suite whenever src/ changes.
# It runs all of tests/, not just tests/test_leakage.py: a leakage-only run
# missed a removed weather-label guard (docs/SEEDED_FAULTS.md, fault 3).
#
# This runs AFTER the edit has landed, so it cannot prevent the write. What
# exit 2 does is send stderr back to Claude as a system message, so the
# failure is in front of the agent immediately and it cannot carry on as if
# the edit were fine. To make "done" itself conditional on green tests, add
# a Stop hook that runs `make test` and exits 2 on failure (check
# stop_hook_active in the payload to avoid looping).
set -uo pipefail

payload=$(cat)
# `python`, not `python3`: on Windows `python3` is often the Microsoft Store
# stub. Backslashes become forward slashes so Windows paths such as
# c:\...\src\features.py match the pattern below; without this the hook
# skipped every edit on Windows without a word.
if ! path=$(printf '%s' "$payload" | python -c \
  'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("file_path","").replace("\\","/"))'); then
  echo "check_leakage hook: could not parse the hook payload with python" >&2
  exit 2
fi

case "$path" in
  */src/*.py) ;;
  *) exit 0 ;;
esac

if ! cd "${CLAUDE_PROJECT_DIR:-.}"; then
  echo "check_leakage hook: cannot cd to project dir '${CLAUDE_PROJECT_DIR:-.}'" >&2
  exit 2
fi
if ! out=$(python -m pytest tests/ -q 2>&1); then
  echo "Tests failed after editing $path:" >&2
  echo "$out" | tail -20 >&2
  exit 2
fi
exit 0
