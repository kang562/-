@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo 未找到运行环境，请先双击“安装依赖.bat”。
  pause
  exit /b 1
)

start "桌面宠物" /b .venv\Scripts\pythonw.exe "桌面宠物.py"
