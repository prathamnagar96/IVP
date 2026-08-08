#!/usr/bin/env bash
# JobRadar Scraper Entrypoint for VPS Cron
# Run this script daily via cron on the VPS
# Example cron: 0 2 * * * /path/to/run_scraper.sh >> /var/log/jobradar-scraper.log 2>&1

set -euo pipefail

# Configuration - override via environment variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${PROJECT_DIR:-$(dirname "$SCRIPT_DIR")}"
VENV_DIR="${VENV_DIR:-$PROJECT_DIR/.venv}"
PYTHON="${PYTHON:-$VENV_DIR/bin/python}"
LOG_FILE="${LOG_FILE:-/var/log/jobradar-scraper.log}"

# Ensure we're in the project directory
cd "$PROJECT_DIR"

# Log function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

# Main
log "Starting JobRadar scraper sync"

# Check if virtual environment exists
if [[ ! -f "$PYTHON" ]]; then
    log "ERROR: Python not found at $PYTHON"
    log "Create virtual environment: python -m venv .venv && .venv/bin/pip install -e ."
    exit 1
fi

# Check if sources.yaml exists
if [[ ! -f "sources.yaml" ]]; then
    log "ERROR: sources.yaml not found in $PROJECT_DIR"
    exit 1
fi

# Run scraper sync
log "Running scraper sync..."
if "$PYTHON" -m jobradar.cli sync-scrape 2>&1 | tee -a "$LOG_FILE"; then
    log "Scraper sync completed successfully"
else
    EXIT_CODE=$?
    log "Scraper sync failed with exit code $EXIT_CODE"
    exit $EXIT_CODE
fi