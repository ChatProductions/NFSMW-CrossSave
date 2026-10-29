@echo off
cd /d "%~dp0"
echo NFSMW CrossSave v0.7.5 - Building standalone Windows executable
echo.
where py >nul 2>nul
if errorlevel 1 goto missing_python
py -3 -m pip install --upgrade pyinstaller
if errorlevel 1 goto failed
py -3 -m PyInstaller --noconfirm --onefile --windowed --clean --name "NFSMW-CrossSave-v0.7.5" --icon "assets\crosssave.ico" --add-data "assets;assets" converter_gui.pyw
if errorlevel 1 goto failed
echo.
echo SUCCESS: dist\NFSMW-CrossSave-v0.7.5.exe
echo This standalone EXE does not require Python on the destination PC.
pause
exit /b 0
:missing_python
echo Install Python 3.10 or newer first from https://www.python.org/downloads/windows/
pause
exit /b 1
:failed
echo EXE build failed. Review the error output above.
pause
exit /b 1
