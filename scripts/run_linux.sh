#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."

if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: python3 is required."
    exit 1
fi

python3 -c "import tkinter" 2>/dev/null || {
    echo "Error: tkinter is required. On Ubuntu/Debian run: sudo apt install python3-tk"
    exit 1
}

exec python3 main.py "$@"
