param([string]$OutputRoot = 'dist')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$allowedRoot = [System.IO.Path]::GetFullPath((Join-Path $projectRoot 'dist'))
$resolvedOutput = [System.IO.Path]::GetFullPath((Join-Path $projectRoot $OutputRoot))
if ($resolvedOutput -ne $allowedRoot -and -not $resolvedOutput.StartsWith($allowedRoot + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'Build output must stay within the project dist directory.'
}
$targetExecutable = Join-Path $resolvedOutput 'QuietReader\QuietReader.exe'
$running = Get-Process QuietReader -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $targetExecutable }
if ($running) {
    $releaseName = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0, 6)
    $resolvedOutput = Join-Path $allowedRoot ('releases\' + $releaseName)
    Write-Host 'Existing application is running; building into a separate release directory.'
}
$appDirectory = Join-Path $resolvedOutput 'QuietReader'
$pythonRoot = & .\.venv\Scripts\python.exe -c "import sys; print(sys.base_prefix)"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$originalPath = $env:PATH
try {
    # Restrict DLL discovery to Python, Qt's own hook paths and Windows.
    # Unrelated tools on PATH may ship incompatible ICU/OpenSSL DLL names.
    $env:PATH = "$projectRoot\.venv\Scripts;$pythonRoot;$pythonRoot\DLLs;$env:SystemRoot\System32;$env:SystemRoot"
    & .\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm --windowed --onedir --name QuietReader --paths src --distpath $resolvedOutput --workpath build run.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    $env:PATH = $originalPath
}
& .\.venv\Scripts\python.exe scripts/collect_notices.py --app-dir $appDirectory
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host ('Built: ' + (Join-Path $appDirectory 'QuietReader.exe') + ' (keep the entire directory)')
