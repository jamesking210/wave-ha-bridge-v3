$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (!(Test-Path '.venv\Scripts\python.exe')) { python -m venv .venv }
& '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt
if ($LASTEXITCODE) { throw 'Dependency installation failed' }
& '.\.venv\Scripts\python.exe' -m unittest discover -s . -p test_bridge.py
if ($LASTEXITCODE) { throw 'Tests failed' }
