$ErrorActionPreference = 'Stop'
Stop-ScheduledTask -TaskName 'WaveHA-Bridge-v3' -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName 'WaveHA-Bridge-v3' -Confirm:$false -ErrorAction SilentlyContinue
Write-Output 'Removed v3 startup task. Files and v2 bridge retained.'
