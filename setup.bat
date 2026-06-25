@echo off
REM 一鍵安裝：建立 venv、安裝後端相依、安裝並建置前端。完成後用 desktop.bat 或 run.bat 啟動。
setlocal
cd /d "%~dp0"

echo [1/4] Creating Python virtualenv (.venv)...
python -m venv .venv || (echo 找不到 python，請先安裝 Python 3.11+ 並加入 PATH。 & pause & exit /b 1)

echo [2/4] Installing backend dependencies...
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt || (echo 後端相依安裝失敗。 & pause & exit /b 1)

echo [3/4] Installing frontend dependencies...
cd frontend
call npm install || (echo npm install 失敗，請先安裝 Node.js 18+。 & cd .. & pause & exit /b 1)

echo [4/4] Building frontend...
call npm run build || (echo 前端建置失敗。 & cd .. & pause & exit /b 1)
cd ..

echo.
echo 安裝完成！接著：
echo   - 桌面 App：雙擊 desktop.bat
echo   - 網頁版： 雙擊 run.bat 後開 http://localhost:8000
pause
