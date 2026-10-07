$ErrorActionPreference='Stop'
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    if(-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {python -m venv --system-site-packages .venv}
    & .venv/Scripts/python.exe -m pip install -r requirements.txt
    if($LASTEXITCODE -ne 0){throw 'Python dependency installation failed'}
    pnpm install --frozen-lockfile
    if($LASTEXITCODE -ne 0){throw 'Node dependency installation failed'}
    & "$PSScriptRoot/atlas.ps1" up -d --build
} finally {Pop-Location}
