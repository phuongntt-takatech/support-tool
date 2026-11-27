@echo off
rem Double-click de mo menu cua Video Template data tool.
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Chua cai dat moi truong Python cho tool.
  echo Lam theo muc "Cai dat (mot lan)" trong README.md, roi mo lai menu.bat.
  pause
  exit /b 1
)
set PYTHONIOENCODING=utf-8
".venv\Scripts\python.exe" vtd.py menu
if errorlevel 1 (
  echo.
  echo Tool da dung bat thuong. Doc thong bao loi o tren, roi nhan phim bat ky de dong cua so.
  pause >nul
)
