@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo A股2026主线识别系统
echo 工作目录：%CD%

if not exist ".venv\Scripts\python.exe" (
  echo 正在创建虚拟环境 .venv ...
  python -m venv .venv
  if errorlevel 1 (
    py -3 -m venv .venv
  )
  if not exist ".venv\Scripts\python.exe" (
    echo 创建虚拟环境失败，请确认已安装 Python 3.11+ 并加入 PATH。
    pause
    exit /b 1
  )
)

call ".venv\Scripts\activate.bat"

python -c "import ashare2026, tzdata, uvicorn" 1>nul 2>nul
if errorlevel 1 (
  echo 正在安装依赖：pip install -e ".[dev]" ...
  python -m pip install -e ".[dev]"
  if errorlevel 1 (
    echo 依赖安装失败。
    pause
    exit /b 1
  )
)

echo 正在打开 http://127.0.0.1:8000
start "" "http://127.0.0.1:8000"
echo 启动控制台，关闭本窗口即停止服务。需要联网获取行情。
python -m ashare2026 serve --port 8000
echo.
pause
