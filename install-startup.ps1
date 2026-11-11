param([switch]$Live)
$ErrorActionPreference = 'Stop'
$python = Join-Path $PSScriptRoot '.venv\Scripts\pythonw.exe'
if (!(Test-Path $python)) { throw 'Run setup.ps1 first' }
# Validate with the same rules as the bridge BEFORE stopping an existing task.
$configCheck = @'
import json,pathlib,sys
sys.path.insert(0,sys.argv[1])
from bridge import validate_config
try:
 c=json.loads((pathlib.Path(sys.argv[1])/'config.json').read_text(encoding='utf-8-sig'))
 validate_config(c)
 if sys.argv[2]=='True' and c['semantics_verified'] is not True:
  raise ValueError('Mute semantics not verified')
except (OSError,ValueError,KeyError):
 print('Invalid configuration or unverified live mode. Check config.json and complete the README mute test.')
 sys.exit(1)
'@
& (Join-Path $PSScriptRoot '.venv\Scripts\python.exe') -c $configCheck $PSScriptRoot ([string]$Live.IsPresent)
if ($LASTEXITCODE) { throw 'Configuration check failed; existing task was not changed' }
$arguments = '"' + (Join-Path $PSScriptRoot 'bridge.py') + '"'
if ($Live) { $arguments += ' --live' }
$action = New-ScheduledTaskAction -Execute $python -Argument $arguments -WorkingDirectory $PSScriptRoot
$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Stop-ScheduledTask -TaskName 'WaveHA-Bridge-v3' -ErrorAction SilentlyContinue
# Wait for Windows to release the previous worker's byte-range lock.
$lockCheck = @'
import pathlib,msvcrt,time,sys
p=pathlib.Path(sys.argv[1])
if not p.exists(): sys.exit(0)
with p.open('r+b') as f:
 for attempt in range(50):
  try:
   f.seek(0); msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
   f.seek(0); msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
   sys.exit(0)
  except OSError: time.sleep(.2)
sys.exit(1)
'@
& (Join-Path $PSScriptRoot '.venv\Scripts\python.exe') -c $lockCheck (Join-Path $PSScriptRoot '.bridge.lock')
if ($LASTEXITCODE) { throw 'A bridge worker is still running. Stop foreground workers and retry.' }
Register-ScheduledTask -TaskName 'WaveHA-Bridge-v3' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName 'WaveHA-Bridge-v3'
Write-Output 'Started WaveHA-Bridge-v3. See logs\bridge.log.'

