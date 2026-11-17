$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$pythonRoot = & .\.venv\Scripts\python.exe -c "import sys; print(sys.base_prefix)"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$originalPath = $env:PATH
try {
    # Restrict DLL discovery to Python, Qt's own hook paths and Windows.
    # Unrelated tools on PATH may ship incompatible ICU/OpenSSL DLL names.
    $env:PATH = "$projectRoot\.venv\Scripts;$pythonRoot;$pythonRoot\DLLs;$env:SystemRoot\System32;$env:SystemRoot"
    & .\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm --windowed --onedir --name QuietReader --paths src --distpath dist --workpath build run.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    $env:PATH = $originalPath
}
& .\.venv\Scripts\python.exe scripts/collect_notices.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host 'Built: dist\QuietReader\QuietReader.exe (keep the entire directory)'
