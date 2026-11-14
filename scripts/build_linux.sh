#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."

echo "[1/4] Checking Python & PyInstaller..."
PY_BIN="${PYTHON:-python3}"
if ! command -v "$PY_BIN" >/dev/null 2>&1; then
    echo "Error: python3 not found. Please install python3 and python3-tk."
    exit 1
fi

"$PY_BIN" -c "import tkinter" 2>/dev/null || {
    echo "Error: tkinter not found. Install it with: sudo apt install python3-tk"
    exit 1
}

"$PY_BIN" -m pip install --quiet --upgrade pyinstaller pillow

echo "[2/4] Generating app icons..."
"$PY_BIN" src/icon_generator.py || true

echo "[3/4] Building standalone Linux ELF binary (release/PersianClockWidget-linux)..."
"$PY_BIN" -m PyInstaller --noconsole --onefile --clean \
    --name "PersianClockWidget-linux" \
    --distpath "release" \
    --workpath "build_linux" \
    --add-data "assets:assets" \
    main.py

echo "[4/4] Cleaning temporary build files & packaging tar.gz..."
rm -rf build_linux PersianClockWidget-linux.spec
chmod +x release/PersianClockWidget-linux

tar -czf release/PersianClockWidget-linux.tar.gz -C release PersianClockWidget-linux

echo "Done! Linux binary ready at: release/PersianClockWidget-linux"
echo "Archive ready at: release/PersianClockWidget-linux.tar.gz"
