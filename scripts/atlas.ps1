$ComposeArgs=$args
$ErrorActionPreference='Stop'
$dockerBin=Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin'
if(Test-Path -LiteralPath $dockerBin){$env:PATH=$dockerBin+';'+$env:PATH}
Push-Location (Split-Path $PSScriptRoot -Parent)
try { & docker compose @ComposeArgs; if($LASTEXITCODE -ne 0){exit $LASTEXITCODE} } finally {Pop-Location}
