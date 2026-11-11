$ErrorActionPreference = 'Stop'
$task = Get-ScheduledTask | Where-Object { $_.TaskName -eq 'WaveHA-Bridge-v3' -and $_.TaskPath -eq '\' }
if ($task) {
    Stop-ScheduledTask -TaskName 'WaveHA-Bridge-v3'
    Unregister-ScheduledTask -TaskName 'WaveHA-Bridge-v3' -Confirm:$false
    Write-Output 'Removed v3 startup task. Project files retained.'
} else {
    Write-Output 'No v3 startup task is installed. Project files retained.'
}

