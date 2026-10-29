$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
py -3 -m pip install --upgrade pyinstaller
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller installation failed' }
py -3 -m PyInstaller --noconfirm --onefile --windowed --clean --name NFSMW-CrossSave-v0.7.3 --icon assets/crosssave.ico --add-data 'assets;assets' converter_gui.pyw
if ($LASTEXITCODE -ne 0) { throw 'EXE build failed' }
Write-Host "Built: $PSScriptRoot\dist\NFSMW-CrossSave-v0.7.3.exe"
