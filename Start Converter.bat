@echo off
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
    py -3 converter_gui.pyw
    goto done
)
where pythonw >nul 2>nul
if not errorlevel 1 (
    start "" pythonw converter_gui.pyw
    goto done
)
echo Python 3.10 or newer is required to run the source version.
echo Get Python from https://www.python.org/downloads/windows/
pause
:done
