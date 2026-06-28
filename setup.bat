@echo off
REM 一鍵安裝：建立 venv、安裝後端相依、安裝並建置前端。完成後用 desktop.bat 或 run.bat 啟動。
setlocal
cd /d "%~dp0"

python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" || (echo 請先安裝 Python 3.11+ 並加入 PATH。 & pause & exit /b 1)

node -e "const [major, minor] = process.versions.node.split('.').map(Number); const ok = (major === 20 && minor >= 19) || (major === 22 && minor >= 13) || major >= 24; if (!ok) { console.error('目前 Node.js ' + process.versions.node + ' 不支援。請安裝 Node.js 20.19+、22.13+ 或 24+。'); process.exit(1); }" || (echo 請先安裝 Node.js 20.19+、22.13+ 或 24+ 並加入 PATH。 & pause & exit /b 1)

npm --version >nul 2>nul || (echo 找不到 npm，請確認 Node.js 安裝完整並加入 PATH。 & pause & exit /b 1)

echo [1/4] Creating Python virtualenv (.venv)...
python -m venv .venv || (echo 建立 Python virtualenv 失敗，請確認 Python venv 可用。 & pause & exit /b 1)

echo [2/4] Installing backend dependencies...
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt || (echo 後端相依安裝失敗。 & pause & exit /b 1)

echo [3/4] Installing frontend dependencies...
cd frontend
call npm install || (echo npm install 失敗，請確認 Node.js / npm 可正常使用。 & cd .. & pause & exit /b 1)

echo [4/4] Building frontend...
call npm run build || (echo 前端建置失敗。 & cd .. & pause & exit /b 1)
cd ..

echo.
echo 安裝完成！接著：
echo   - 桌面 App：雙擊 desktop.bat
echo   - 網頁版： 雙擊 run.bat 後開 http://localhost:8000
pause
