@echo off
cd /d "%~dp0\.."

echo [0/4] Stopping any old running widget instance...
taskkill /F /IM PersianClockWidget.exe >nul 2>&1

set "PY_EXE=C:\Users\sh.bamyar\AppData\Local\Python\pythoncore-3.14-64\python.exe"
if not exist "%PY_EXE%" set "PY_EXE=python"

echo [1/4] Generating Persian Clock and Calendar Icon...
"%PY_EXE%" src\icon_generator.py

echo [2/4] Building standalone release\PersianClockWidget.exe (with Vazir font, GUID, Hover, and MP3 sounds)...
"%PY_EXE%" -m PyInstaller --noconsole --onefile --clean ^
    --name "PersianClockWidget" ^
    --distpath "release" ^
    --workpath "build" ^
    --icon "assets\icons\app_icon.ico" ^
    --add-data "assets;assets" ^
    --hidden-import win32api ^
    --hidden-import win32con ^
    --hidden-import win32gui ^
    main.py

echo [3/4] Cleaning temporary build artifacts...
if exist "build" rmdir /s /q "build"
if exist "PersianClockWidget.spec" del /f /q "PersianClockWidget.spec"
if exist "release\config.json" del /f /q "release\config.json"

echo [4/4] Launching the new release\PersianClockWidget.exe...
if exist "release\PersianClockWidget.exe" (
    start "" "release\PersianClockWidget.exe"
    echo Done! New PersianClockWidget.exe is built and running!
) else (
    echo Build failed! Please check the output above.
    pause
)
