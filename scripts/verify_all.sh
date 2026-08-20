#!/usr/bin/env bash
# ==============================================================================
# Netools Suite - Deterministic Verification Gate
# Runs compilation check, unit & integration tests, socket checks, and packaging.
# ==============================================================================
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BASE_DIR"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}======================================================${NC}"
echo -e "${BLUE}   ⚡ Netools Suite — Deterministic Verification Gate  ${NC}"
echo -e "${BLUE}======================================================${NC}"

# 1. Bytecode Compilation Check
echo -e "\n${YELLOW}▶ [1/5] Checking Python Bytecode & Syntax Compilation...${NC}"
python3 -m compileall -q netools tests netools/__main__.py
echo -e "${GREEN}✓ Bytecode & syntax compilation passed cleanly.${NC}"

# 2. Code Quality & Anti-Hardcoding Audit
echo -e "\n${YELLOW}▶ [2/5] Running Code Hygiene & Anti-Hardcoding Audit...${NC}"
# Check for forbidden mockup patterns
FORBIDDEN_HITS=$(grep -rEi "FIXME|TODO_CRITICAL|dummy_token|sample_proxy" netools/ tests/ || true)
if [ -n "$FORBIDDEN_HITS" ]; then
    echo -e "${RED}✗ Forbidden mockup or placeholder detected:${NC}"
    echo "$FORBIDDEN_HITS"
    exit 1
fi
echo -e "${GREEN}✓ Code hygiene & anti-hardcoding audit passed.${NC}"

# 3. Ruff Lint Gate
echo -e "\n${YELLOW}▶ [3/5] Running Ruff Lint Gate...${NC}"
if command -v ruff >/dev/null 2>&1; then
    ruff check netools tests
else
    .venv/bin/ruff check netools tests
fi
echo -e "${GREEN}✓ Ruff lint passed.${NC}"

# 4. Unit, Socket & GUI Integration Test Suite
echo -e "\n${YELLOW}▶ [4/5] Running Unit, Socket & GUI Verification Suite...${NC}"
python3 tests/verify_suite.py
echo -e "${GREEN}✓ All core, network socket, and GUI module tests passed.${NC}"

# 5. CLI Smoke Test
echo -e "\n${YELLOW}▶ [5/5] Executing CLI Smoke Commands...${NC}"
python3 -m netools dns presets > /dev/null
python3 -m netools pac status > /dev/null
echo -e "${GREEN}✓ CLI command smoke test passed.${NC}"

# Optional AppImage Build
if [[ "${1:-}" == "--build" ]]; then
    echo -e "\n${YELLOW}▶ [BONUS] Packaging & Verifying Standalone AppImage...${NC}"
    ./scripts/build_appimage.sh
    if [ -f "dist/Netools-x86_64.AppImage" ]; then
        echo -e "${GREEN}✓ AppImage binary verified at dist/Netools-x86_64.AppImage${NC}"
    else
        echo -e "${RED}✗ AppImage binary build failed!${NC}"
        exit 1
    fi
fi

echo -e "\n${GREEN}======================================================${NC}"
echo -e "${GREEN}   ✅ [ALL GATES PASSED] Netools Suite is 100% Verified! ${NC}"
echo -e "${GREEN}======================================================${NC}"
