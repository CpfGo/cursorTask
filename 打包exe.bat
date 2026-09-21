@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo A股2026 本地打包 Windows 可执行文件
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

echo 正在安装打包依赖：python -m pip install -e ".[pack]" ...
python -m pip install -e ".[pack]"
if errorlevel 1 (
  echo 依赖安装失败。
  pause
  exit /b 1
)

echo 正在打包：python -m PyInstaller ashare2026.spec --noconfirm
python -m PyInstaller ashare2026.spec --noconfirm
if errorlevel 1 (
  echo 打包失败。
  pause
  exit /b 1
)

echo.
echo 打包成功。可执行文件：
echo %CD%\dist\AShare2026\AShare2026.exe
echo 正在打开 dist\AShare2026
explorer dist\AShare2026
echo.
pause
