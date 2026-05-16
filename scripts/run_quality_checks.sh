#!/bin/bash
# Code Quality Check Script
# This script runs all code quality checks before commits

set -e

echo "🔍 Running Code Quality Checks..."
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track if any checks fail
FAILED=0

# Check 1: Ruff linting
echo "Running Ruff linting..."
if command -v ruff &> /dev/null; then
    if ruff check backend/; then
        echo -e "${GREEN}✓ Ruff checks passed${NC}"
    else
        echo -e "${RED}✗ Ruff checks failed${NC}"
        FAILED=1
    fi
else
    echo -e "${YELLOW}⚠ Ruff not installed, skipping${NC}"
fi
echo ""

# Check 2: Type checking
echo "Running MyPy type checking..."
if command -v mypy &> /dev/null; then
    if mypy backend/app --ignore-missing-imports; then
        echo -e "${GREEN}✓ MyPy checks passed${NC}"
    else
        echo -e "${RED}✗ MyPy checks failed${NC}"
        FAILED=1
    fi
else
    echo -e "${YELLOW}⚠ MyPy not installed, skipping${NC}"
fi
echo ""

# Check 3: Security audit
echo "Running security audit..."
if command -v pip-audit &> /dev/null; then
    if pip-audit --local -r backend/requirements.txt; then
        echo -e "${GREEN}✓ Security audit passed${NC}"
    else
        echo -e "${RED}✗ Security vulnerabilities found${NC}"
        FAILED=1
    fi
else
    echo -e "${YELLOW}⚠ pip-audit not installed, skipping${NC}"
fi
echo ""

# Check 4: Tests
echo "Running tests..."
if python -m pytest backend/tests/ -v --tb=short -x; then
    echo -e "${GREEN}✓ All tests passed${NC}"
else
    echo -e "${RED}✗ Tests failed${NC}"
    FAILED=1
fi
echo ""

# Final result
echo "========================================="
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ All checks passed! Ready to commit.${NC}"
    exit 0
else
    echo -e "${RED}❌ Some checks failed. Please fix the issues above.${NC}"
    exit 1
fi
