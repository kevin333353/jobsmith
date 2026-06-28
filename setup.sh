#!/usr/bin/env bash
# 一鍵安裝（macOS / Linux / Git Bash）：建 venv、裝後端相依、裝並建前端。
set -e
cd "$(dirname "$0")"

echo "[1/4] Creating Python virtualenv (.venv)..."
python -m venv .venv

# venv 的 python 路徑跨平台不同（Windows: Scripts；其餘: bin）。
if [ -f .venv/bin/python ]; then PY=.venv/bin/python; else PY=.venv/Scripts/python.exe; fi

echo "[2/4] Installing backend dependencies..."
if command -v apt-get &>/dev/null; then
    sudo apt-get update -qq && sudo apt-get install -y python-is-python3 python3.12-venv curl
    # apt's bundled Node is too old for Vite 8 (needs 20.19+ or 22.12+); use NodeSource
    curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
    sudo apt-get install -y nodejs
elif command -v brew &>/dev/null; then
    brew install python@3.12 node@22
    brew link node@22 --force --overwrite
elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    echo "Windows detected: ensure Python 3.12 and Node.js 22+ are installed manually." >&2
else
    echo "Unsupported package manager. Please install Python 3.12 and Node.js 22+ manually." >&2
fi
"$PY" -m pip install --upgrade pip
"$PY" -m pip install -r requirements.txt

echo "[3/4] Installing frontend dependencies..."
cd frontend && npm install

echo "[4/4] Building frontend..."
npm run build
cd ..

echo
echo "安裝完成！啟動方式："
echo "  - 桌面 App： $PY desktop.py"
echo "  - 網頁版：   $PY -m uvicorn app.server:app --port 8000  → http://localhost:8000"
