@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo 未找到运行环境，请先双击“安装依赖.bat”。
  pause
  exit /b 1
)

call .venv\Scripts\activate.bat
pyinstaller --noconfirm --clean --onefile --windowed --name "桌面宠物" --add-data "assets;assets" --hidden-import pynput.keyboard._win32 --hidden-import pynput.mouse._win32 "桌面宠物.py"
if errorlevel 1 (
  echo.
  echo 打包失败。
  pause
  exit /b 1
)

echo.
echo 打包完成：dist\桌面宠物.exe
pause
