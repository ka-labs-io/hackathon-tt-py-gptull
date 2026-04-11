#!/usr/bin/env bash
# run_quality_checks.sh — Code quality evaluation suite for the tt translator.
#
# Runs all checks and prints a results table. Exits non-zero if any check fails.
#
# Usage:
#   bash evaluate/checks/run_quality_checks.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

PROJECT="${PROJECT_NAME:-ghostfolio}"
echo "--- Code quality checks (PROJECT_NAME=$PROJECT) ---"
echo "  Translation:  $ROOT_DIR/translations/${PROJECT}_pytx"
echo "  Example:      $ROOT_DIR/translations/${PROJECT}_pytx_example"
echo "  tt scaffold:  $ROOT_DIR/tt/tt/scaffold/${PROJECT}_pytx"
echo ""

CHECK_NAMES=()
CHECK_STATUSES=()
FAILURE_OUTPUTS=()
FAILURES=0

run_check() {
  local name="$1"; shift
  local exit_code=0
  local output
  output=$(uv run --project "$ROOT_DIR/tt" python "$@" 2>&1) || exit_code=$?
  CHECK_NAMES+=("$name")
  if [ "$exit_code" -eq 0 ]; then
    CHECK_STATUSES+=("OK")
    FAILURE_OUTPUTS+=("")
  else
    CHECK_STATUSES+=("FAIL")
    FAILURE_OUTPUTS+=("$output")
    FAILURES=$((FAILURES + 1))
  fi
}

RULES_DIR="$SCRIPT_DIR/implementation_rules"

run_check "LLM usage in tt/"            "$RULES_DIR/detect_llm_usage.py"
run_check "Direct mappings in tt/"      "$RULES_DIR/detect_direct_mappings.py"
run_check "Explicit implementation"     "$RULES_DIR/detect_explicit_implementation.py"
run_check "Financial logic in scaffold" "$RULES_DIR/detect_explicit_financial_logic.py"
run_check "Scaffold bloat"              "$RULES_DIR/detect_scaffold_bloat.py"
run_check "Code block copying"          "$RULES_DIR/detect_code_block_copying.py"
run_check "Interface compliance"        "$RULES_DIR/detect_interface_violation.py"
run_check "Wrapper modification"        "$RULES_DIR/detect_wrapper_modification.py"
run_check "Evaluate folder unchanged"  "$RULES_DIR/detect_evaluate_modification.py"
run_check "Template file bypass"       "$RULES_DIR/detect_pysrc_templates.py"
run_check "Premade calculator"         "$RULES_DIR/detect_premade_calculator.py"
run_check "String-literal smuggling"   "$RULES_DIR/detect_string_literal_smuggling.py"

if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
  run_check "Explicit implementation LLM review" "$RULES_DIR/detect_explicit_implementation_llm.py"
else
  CHECK_NAMES+=("Explicit implementation LLM review")
  CHECK_STATUSES+=("SKIPPED")
  FAILURE_OUTPUTS+=("")
fi

# ---------------------------------------------------------------------------
# Print results table
# ---------------------------------------------------------------------------
COL=38
SEP="$(printf '%*s' $COL '' | tr ' ' '-')"
printf "%-${COL}s %s\n" "Check" "Status"
printf "%-${COL}s %s\n" "$SEP" "--------"
for i in "${!CHECK_NAMES[@]}"; do
  printf "%-${COL}s %s\n" "${CHECK_NAMES[$i]}" "${CHECK_STATUSES[$i]}"
done
echo ""

# Print failure details after the table
for i in "${!CHECK_NAMES[@]}"; do
  if [ "${CHECK_STATUSES[$i]}" = "FAIL" ]; then
    echo "--- ${CHECK_NAMES[$i]} ---"
    echo "${FAILURE_OUTPUTS[$i]}"
    echo ""
  fi
done

if [ "$FAILURES" -gt 0 ]; then
  echo "Code quality checks: $FAILURES check(s) FAILED"
  exit 1
else
  echo "Code quality checks: all OK"
fi
