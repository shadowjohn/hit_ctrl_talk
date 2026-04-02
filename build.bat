@echo off
setlocal

cd /d "%~dp0"

echo [build] working dir: %cd%

if not exist "hit_ctrl_talk.py" (
    echo [build] error: hit_ctrl_talk.py not found
    exit /b 1
)


copy /y icon_bak.ico icon.ico

where python >nul 2>nul
if errorlevel 1 (
    echo [build] error: python not found in PATH
    exit /b 1
)

echo [build] cleaning old output...
rem if exist "build" rmdir /s /q "build"
rem if exist "dist" rmdir /s /q "dist"
if exist "hit_ctrl_talk.spec" del /q "hit_ctrl_talk.spec"

echo [build] building onefile exe with PyInstaller...
python -m PyInstaller ^
    --clean ^
    --noconfirm ^
    --onefile ^
    --console ^
    --name hit_ctrl_talk ^
    --icon icon.ico ^
    --collect-data faster_whisper ^
    --hidden-import pythoncom ^
    --hidden-import win32gui ^
    --hidden-import win32con ^
    --hidden-import win32api ^
    hit_ctrl_talk.py

if errorlevel 1 (
    echo [build] failed
    exit /b 1
)

echo [build] done
echo [build] output: %cd%\dist\hit_ctrl_talk.exe
exit /b 0
