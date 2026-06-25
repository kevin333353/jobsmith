#!/usr/bin/env bash
# 一鍵安裝（macOS / Linux / Git Bash）：建 venv、裝後端相依、裝並建前端。
set -e
cd "$(dirname "$0")"

echo "[1/4] Creating Python virtualenv (.venv)..."
python -m venv .venv

# venv 的 python 路徑跨平台不同（Windows: Scripts；其餘: bin）。
if [ -f .venv/bin/python ]; then PY=.venv/bin/python; else PY=.venv/Scripts/python.exe; fi

echo "[2/4] Installing backend dependencies..."
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
