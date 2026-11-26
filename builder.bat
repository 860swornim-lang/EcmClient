@echo off
setlocal EnableDelayedExpansion
title ECM Launcher - Builder
cd /d "%~dp0"

echo ==========================================
echo   ECM Launcher - launcher and Fabric client builder
echo ==========================================
echo.

rem ---- 1. Python check ------------------------------------------------------
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY ( where python >nul 2>nul && set "PY=python" )
if not defined PY (
    echo [ERROR] Python 3.10+ was not found.
    echo         Install it from https://www.python.org/downloads/ and tick "Add python.exe to PATH".
    pause
    exit /b 1
)

rem ---- 2. Virtual environment ----------------------------------------------
if not exist ".venv\Scripts\python.exe" (
    echo [1/5] Creating virtual environment ...
    %PY% -m venv .venv || goto :fail
)
call ".venv\Scripts\activate.bat"

echo [2/5] Installing requirements ...
python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt pyinstaller || goto :fail

rem ---- 3. Build both ECM Fabric client jars -------------------------------
echo [3/6] Building Fabric client mods (JDK 25 required) ...
javac -version 2>&1 | findstr /R /C:"javac 25\." /C:"javac 26\." >nul || (
    echo [ERROR] JDK 25 or newer is required to build the Fabric client mods.
    echo         Install a JDK and set JAVA_HOME before building.
    goto :fail
)
if not exist client-mods mkdir client-mods
pushd .project
call gradlew.bat build || (popd & goto :fail)
copy /y "build\libs\ecm-client-1.1.0.jar" "..\client-mods\ecm-client-1.21.11.jar" >nul || (popd & goto :fail)
popd
pushd .project\26.2
call gradlew.bat build || (popd & goto :fail)
copy /y "build\libs\ecm-client-1.1.0.jar" "..\..\client-mods\ecm-client-26.2.jar" >nul || (popd & goto :fail)
popd

rem ---- 4. Logos -------------------------------------------------------------
if not exist "assets\logo\applogo\app_icon.ico" (
    echo [4/6] Generating logos ...
    python tools\make_logos.py || goto :fail
) else (
    echo [4/6] Logos found.
)

rem ---- 5. Build -------------------------------------------------------------
echo [5/6] Building ECMLauncher.exe (this takes a minute) ...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
pyinstaller --noconfirm --clean --onefile --windowed ^
    --name ECMLauncher ^
    --icon "assets\logo\applogo\app_icon.ico" ^
    --add-data "assets;assets" ^
    --add-data "client-mods;client-mods" ^
    --collect-all customtkinter ^
    --collect-all minecraft_launcher_lib ^
    --collect-all keyring ^
    --copy-metadata keyring ^
    --hidden-import PIL._tkinter_finder ^
    --hidden-import PIL._imagingtk ^
    --hidden-import PIL.ImageTk ^
    main.py || goto :fail

rem ---- 6. Collect ------------------------------------------------------------
echo [6/6] Copying result ...
if not exist release mkdir release
copy /y "dist\ECMLauncher.exe" "release\ECMLauncher.exe" >nul

echo.
echo ==========================================
echo   Done!  release\ECMLauncher.exe
echo   Game data is stored in a .ecmbro folder next to the exe
echo ==========================================
explorer release
pause
exit /b 0

:fail
echo.
echo [ERROR] Build failed - scroll up to see why.
pause
exit /b 1
