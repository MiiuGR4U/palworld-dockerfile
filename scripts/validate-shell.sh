#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "============================================================"
echo "  Auditing Shell Scripts in ${PROJECT_DIR}"
echo "============================================================"

ERRORS=0

for script in "${PROJECT_DIR}"/*.sh; do
    if [[ -f "${script}" ]]; then
        filename="$(basename "${script}")"
        echo -n "Checking ${filename}... "
        if bash -n "${script}" 2>/dev/null; then
            echo "✓ [OK]"
        else
            echo "❌ [FAIL] Syntax error in ${filename}"
            bash -n "${script}"
            ERRORS=$((ERRORS + 1))
        fi
    fi
done

echo "============================================================"
if (( ERRORS > 0 )); then
    echo "Shell Validation Failed: ${ERRORS} script(s) had syntax errors."
    exit 1
else
    echo "All shell scripts passed syntax validation successfully!"
    exit 0
fi
