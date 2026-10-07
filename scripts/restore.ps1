$ErrorActionPreference='Stop'
if($args.Count -lt 2){throw 'Usage: restore.ps1 BACKUP_PATH NEW_EMPTY_STATE_PATH'}
& "$PSScriptRoot/atlas.ps1" exec -e "ATLAS_STATE=$($args[1])" scheduler python -m service.manage restore $args[0]
if($LASTEXITCODE -ne 0){throw 'Restore failed'}
