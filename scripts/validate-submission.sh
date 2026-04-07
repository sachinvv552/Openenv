#!/usr/bin/env bash
#
# validate-submission.sh — OpenEnv Submission Validator
#

set -uo pipefail

DOCKER_BUILD_TIMEOUT=600
if [ -t 1 ]; then
  RED='\033[0;31m'
  GREEN='\033[0;32m'
  YELLOW='\033[1;33m'
  BOLD='\033[1m'
  NC='\033[0m'
else
  RED=''
  GREEN=''
  YELLOW=''
  BOLD=''
  NC=''
fi

PASS_COUNT=0
FAIL_COUNT=0

pass() {
  echo -e "${GREEN}[PASS]${NC} $1"
  PASS_COUNT=$((PASS_COUNT + 1))
}

warn() {
  echo -e "${YELLOW}[WARN]${NC} $1"
}

fail() {
  echo -e "${RED}[FAIL]${NC} $1"
  FAIL_COUNT=$((FAIL_COUNT + 1))
}

section() {
  echo
  echo -e "${BOLD}== $1 ==${NC}"
}

usage() {
  cat <<EOF
Usage:
  $0 <ping_url> [repo_dir]
EOF
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    fail "Missing required command: $1"
    return 1
  fi
  return 0
}

PING_URL="${1:-}"
REPO_DIR="${2:-.}"

if [ -z "$PING_URL" ]; then
  usage
  exit 1
fi

section "Checking prerequisites"
require_cmd curl || true
require_cmd docker || true
require_cmd python || require_cmd python3 || true

if command -v openenv >/dev/null 2>&1; then
  pass "openenv CLI found"
elif python -c "import openenv" >/dev/null 2>&1 2>/dev/null; then
  pass "openenv Python package found"
else
  fail "openenv not found. Install with: pip install openenv-core"
fi

section "Checking repository structure"

[ -f "$REPO_DIR/openenv.yaml" ] && pass "Found openenv.yaml" || fail "Missing openenv.yaml"
[ -f "$REPO_DIR/Dockerfile" ] && pass "Found Dockerfile" || fail "Missing Dockerfile"
[ -f "$REPO_DIR/inference.py" ] && pass "Found inference.py" || fail "Missing inference.py in repo root"
[ -f "$REPO_DIR/README.md" ] && pass "Found README.md" || warn "README.md not found"

section "Pinging Hugging Face Space"

HTTP_CODE="$(curl -L -s -o /tmp/openenv_space_response.txt -w "%{http_code}" "$PING_URL" || echo "000")"
if [ "$HTTP_CODE" = "200" ]; then
  pass "Space responded with HTTP 200 at $PING_URL"
else
  fail "Space ping failed. Expected HTTP 200, got $HTTP_CODE"
fi

RESET_CODE="$(curl -L -s -o /tmp/openenv_reset_response.txt -w "%{http_code}" \
  -X POST "$PING_URL/reset" \
  -H "Content-Type: application/json" \
  -d '{}' || echo "000")"

if [ "$RESET_CODE" = "200" ]; then
  pass "Space /reset endpoint responded with HTTP 200"
else
  warn "Space /reset endpoint did not return HTTP 200 (got $RESET_CODE). Verify your API route."
fi

section "Validating OpenEnv spec"

if command -v openenv >/dev/null 2>&1; then
  (
    cd "$REPO_DIR" || exit 1
    openenv validate
  )
  VALIDATE_EXIT=$?
else
  VALIDATE_EXIT=127
fi

if [ "$VALIDATE_EXIT" -eq 0 ]; then
  pass "openenv validate passed"
else
  fail "openenv validate failed"
fi

section "Building Docker image"

IMAGE_TAG="openenv-submission-validator:latest"
if command -v timeout >/dev/null 2>&1; then
  timeout "$DOCKER_BUILD_TIMEOUT" docker build -t "$IMAGE_TAG" "$REPO_DIR"
  BUILD_EXIT=$?
else
  warn "'timeout' command not found; running docker build without timeout"
  docker build -t "$IMAGE_TAG" "$REPO_DIR"
  BUILD_EXIT=$?
fi

if [ "$BUILD_EXIT" -eq 0 ]; then
  pass "Docker build succeeded"
else
  fail "Docker build failed"
fi

section "Checking task and grader hints"

TASK_COUNT="$(find "$REPO_DIR" -type f \( -name "*.py" -o -name "*.yaml" -o -name "*.yml" \) 2>/dev/null | xargs grep -E "grader|task" 2>/dev/null | wc -l | tr -d ' ')"

if [ "${TASK_COUNT:-0}" -ge 3 ]; then
  pass "Repository appears to define at least 3 task/grader references"
else
  warn "Could not confidently detect 3 tasks/graders. Verify manually."
fi

section "Summary"
echo "Passed: $PASS_COUNT"
echo "Failed: $FAIL_COUNT"

if [ "$FAIL_COUNT" -gt 0 ]; then
  echo
  echo -e "${RED}${BOLD}Validation failed.${NC}"
  exit 1
fi

echo
echo -e "${GREEN}${BOLD}Validation passed.${NC}"
