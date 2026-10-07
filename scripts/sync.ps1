$Source=$args
& "$PSScriptRoot/atlas.ps1" exec -T data python -m service.pipeline @Source
