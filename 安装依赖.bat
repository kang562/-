@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  py -3.12 -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo 依赖安装失败。请确认网络连接和 Python 3.12 已安装。
  pause
  exit /b 1
)

echo.
echo 安装完成。现在可双击“运行桌宠.bat”。
pause
