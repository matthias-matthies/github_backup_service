#!/usr/bin/env bash
# setup.sh – Bootstrap the GitHub Backup Service on Linux / macOS
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "==> Setting up GitHub Backup Service in $PROJECT_DIR"

# ── Python version check ────────────────────────────────────────────────────
PYTHON=$(command -v python3 || command -v python)
if [ -z "$PYTHON" ]; then
  echo "ERROR: Python 3.8+ is required but was not found." >&2
  exit 1
fi

PY_VERSION=$("$PYTHON" -c 'import sys; print("%d.%d" % sys.version_info[:2])')
echo "--> Python version: $PY_VERSION"

# ── Virtual environment ─────────────────────────────────────────────────────
VENV_DIR="$PROJECT_DIR/.venv"
if [ ! -d "$VENV_DIR" ]; then
  echo "--> Creating virtual environment at $VENV_DIR"
  "$PYTHON" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
echo "--> Virtual environment activated."

# ── Dependencies ────────────────────────────────────────────────────────────
echo "--> Installing dependencies from requirements.txt …"
pip install --upgrade pip --quiet
pip install -r "$PROJECT_DIR/requirements.txt" --quiet
echo "--> Dependencies installed."

# ── Directory structure ─────────────────────────────────────────────────────
echo "--> Creating runtime directories …"
mkdir -p "$PROJECT_DIR/backup/organizations"
mkdir -p "$PROJECT_DIR/backup/repositories"
mkdir -p "$PROJECT_DIR/backup/metadata"
mkdir -p "$PROJECT_DIR/backup/assets"
mkdir -p "$PROJECT_DIR/logs"

# ── Config template ─────────────────────────────────────────────────────────
if [ ! -f "$PROJECT_DIR/config.yml" ]; then
  echo "--> Copying config.example.yml → config.yml"
  cp "$PROJECT_DIR/config.example.yml" "$PROJECT_DIR/config.yml"
  echo "    Edit $PROJECT_DIR/config.yml and fill in your credentials."
fi

echo ""
echo "==> Setup complete!"
echo "    Activate the environment:  source .venv/bin/activate"
echo "    Run a backup:              python -m src.backup --config config.yml"
