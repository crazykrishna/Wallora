```bat
@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Wallora Setup
mode con: cols=75 lines=30
color 0B

:: ==========================================
:: WALLORA - COLORFUL SETUP INSTALLER
:: ==========================================

cls
call :banner

call :info "Initializing Wallora setup..."
timeout /t 1 >nul

:: Check Python
call :step "Checking Python installation..."

where python >nul 2>nul
if errorlevel 1 (
    call :error "Python was not found!"
    call :warning "Install Python and ensure it is added to PATH."
    goto FAIL
)

call :success "Python is available."

:: Install libraries
call :step "Installing required Python libraries..."

python -m pip install --upgrade pystray pillow

if errorlevel 1 (
    call :error "Failed to install Python libraries."
    goto FAIL
)

call :success "Python libraries installed."

:: Check for existing MPV
if exist "%~dp0mpv.exe" (
    call :success "MPV executable already exists."
    goto START_WALLORA
)

where mpv >nul 2>nul
if not errorlevel 1 (
    call :success "MPV is available through PATH."
    goto START_WALLORA
)

:: Download MPV
call :step "Downloading MPV package..."

set "MPV_ARCHIVE=%TEMP%\wallora_mpv.7z"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
"$ProgressPreference = 'Continue'; try { Invoke-WebRequest -Uri 'https://github.com/zhongfly/mpv-winbuild/releases/download/2026-10-17-6f605372b9/mpv-x86_64-20261017-git-6f605372b9.7z' -OutFile '%MPV_ARCHIVE%' -ErrorAction Stop; exit 0 } catch { Write-Host ('Download error: ' + $_.Exception.Message) -ForegroundColor Red; exit 1 }"

if errorlevel 1 (
    call :error "MPV download failed."
    goto FAIL
)

if not exist "%MPV_ARCHIVE%" (
    call :error "MPV archive was not downloaded."
    goto FAIL
)

call :success "MPV download completed."

:: Extract MPV
call :step "Extracting MPV package..."

where tar >nul 2>nul
if errorlevel 1 (
    call :error "The Windows tar command is unavailable."
    goto FAIL
)

tar -xf "%MPV_ARCHIVE%" -C "%CD%"

if errorlevel 1 (
    call :error "MPV extraction failed."
    goto FAIL
)

del "%MPV_ARCHIVE%" >nul 2>nul

if not exist "%~dp0mpv.exe" (
    call :error "mpv.exe was not found in the project root."
    call :warning "The archive may have extracted into a subfolder."
    goto FAIL
)

call :success "MPV extracted successfully."

:START_WALLORA

call :step "Launching Wallora..."

start "" pythonw "%~dp0wallora.py"

if errorlevel 1 (
    call :error "Could not launch Wallora."
    goto FAIL
)

call :success "Wallora has been launched!"
call :info "Look for the Wallora icon in your system tray."

echo.
call :line
call :center "  WALLORA IS READY"
call :center "  Your Desktop, Your Atmosphere."
call :line
echo.

timeout /t 3 >nul
endlocal
exit /b 0

:: ==========================================
:: HELPER FUNCTIONS
:: ==========================================

:banner
echo.
call :line
call :center "  WALLORA SETUP  "
call :line
echo.
exit /b

:line
echo ==========================================================================
exit /b

:center
echo                         %~1
exit /b

:info
powershell -NoProfile -Command "Write-Host '[INFO] %~1' -ForegroundColor Cyan"
exit /b

:step
powershell -NoProfile -Command "Write-Host ''; Write-Host '[....] %~1' -ForegroundColor Magenta"
exit /b

:success
powershell -NoProfile -Command "Write-Host '[ OK ] %~1' -ForegroundColor Green"
exit /b

:warning
powershell -NoProfile -Command "Write-Host '[WARN] %~1' -ForegroundColor Yellow"
exit /b

:error
powershell -NoProfile -Command "Write-Host '[FAIL] %~1' -ForegroundColor Red"
exit /b

:FAIL
echo.
call :line
call :error "Setup could not complete."
call :warning "Resolve the issue above and run setup again."
call :line
echo.
pause
endlocal
exit /b 1
```
