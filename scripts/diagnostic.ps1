$ErrorActionPreference='Continue'
Get-CimInstance Win32_OperatingSystem | Select-Object Caption,OSArchitecture,FreePhysicalMemory,TotalVisibleMemorySize
Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM
Get-PSDrive C | Select-Object Used,Free
Get-NetTCPConnection -State Listen | Where-Object LocalPort -In 3000,5173,8787,11434 | Select-Object LocalAddress,LocalPort
& "$PSScriptRoot\atlas.ps1" version
& "$PSScriptRoot\atlas.ps1" ps
