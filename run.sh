#!/usr/bin/env bash
# Sets up dependencies and runs the Streamlit app.
set -euo pipefail

cd "$(dirname "$0")"

VENV_DIR=".venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment in $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "Installing dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

echo "Starting Streamlit app..."
exec streamlit run app.py
