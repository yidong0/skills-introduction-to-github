#!/usr/bin/env bash
# Research Data Collector — Cloud launcher (Hermes / OpenClaw)
# Usage:
#   ./run.sh                          # full run, all enabled sources
#   ./run.sh --sources arxiv pubmed   # selected sources only
#   ./run.sh --format csv             # override output format
#   COLLECTOR_CONFIG=custom.yaml ./run.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

CONFIG="${COLLECTOR_CONFIG:-config/config.yaml}"
PYTHON="${COLLECTOR_PYTHON:-python3}"

echo "=== Research Data Collector ==="
echo "Config : $CONFIG"
echo "Python : $($PYTHON --version)"
echo "Time   : $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "================================"

# Install dependencies if needed
if ! "$PYTHON" -c "import yaml" 2>/dev/null; then
    echo "[setup] Installing pyyaml …"
    "$PYTHON" -m pip install --quiet pyyaml
fi

# Create output directory
mkdir -p output

# Run collector
"$PYTHON" main.py --config "$CONFIG" "$@"

echo ""
echo "Output files:"
ls -lh output/ 2>/dev/null || echo "(no output files found)"
