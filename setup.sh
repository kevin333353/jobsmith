#!/usr/bin/env bash
# 一鍵安裝（macOS / Linux / Git Bash）：建 venv、裝後端相依、裝並建前端。
set -e
cd "$(dirname "$0")"

NODE_REQUIREMENT="Node.js 20.19+, 22.13+, or 24+"

find_python() {
    if [ -n "${PYTHON:-}" ]; then
        printf '%s\n' "$PYTHON"
        return
    fi
    for cmd in python3.12 python3.11 python3 python; do
        if command -v "$cmd" >/dev/null 2>&1; then
            printf '%s\n' "$cmd"
            return
        fi
    done
    return 1
}

PYTHON_CMD="$(find_python)" || {
    echo "找不到 Python。請先安裝 Python 3.11+ 並加入 PATH。" >&2
    exit 1
}

"$PYTHON_CMD" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" || {
    "$PYTHON_CMD" --version >&2 || true
    echo "Python 版本過舊，請安裝 Python 3.11+。" >&2
    exit 1
}

if ! command -v node >/dev/null 2>&1; then
    echo "找不到 Node.js。請先安裝 $NODE_REQUIREMENT 並加入 PATH。" >&2
    exit 1
fi

node -e "const [major, minor] = process.versions.node.split('.').map(Number); const ok = (major === 20 && minor >= 19) || (major === 22 && minor >= 13) || major >= 24; if (!ok) { console.error('目前 Node.js ' + process.versions.node + ' 不支援。請安裝 $NODE_REQUIREMENT。'); process.exit(1); }"

if ! command -v npm >/dev/null 2>&1; then
    echo "找不到 npm。請確認 Node.js 安裝完整，並將 npm 加入 PATH。" >&2
    exit 1
fi

echo "[1/4] Creating Python virtualenv (.venv)..."
"$PYTHON_CMD" -m venv .venv || {
    echo "建立 Python virtualenv 失敗。" >&2
    echo "Debian/Ubuntu 若缺少 venv，請先執行：sudo apt install python3-venv" >&2
    exit 1
}

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
