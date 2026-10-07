param([string]$Name=('backup-'+(Get-Date -Format 'yyyyMMdd-HHmmss')))
if($Name -notmatch '^[a-zA-Z0-9-]+$'){throw 'Invalid backup name'}
& "$PSScriptRoot/atlas.ps1" exec -T data python -m service.manage backup "/backups/$Name"
if($LASTEXITCODE -eq 0){& "$PSScriptRoot/atlas.ps1" cp "data:/backups/$Name" "$Name"}
