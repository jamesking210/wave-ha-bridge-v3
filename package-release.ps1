# Explicit allowlist: personal configuration and runtime files cannot enter the ZIP.
$ErrorActionPreference = 'Stop'
$files = @('README.md', 'bridge.py', 'configure.py', 'config.example.json',
    'requirements.txt', 'setup.ps1', 'install-startup.ps1', 'uninstall-startup.ps1',
    'dry-run.cmd', 'test_bridge.py', 'package-release.ps1', '.gitignore',
    'examples/home-assistant.yaml')
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$dist = Join-Path $PSScriptRoot 'dist'
New-Item -ItemType Directory -Path $dist -Force | Out-Null
$output = Join-Path $dist 'wave-ha-bridge-v3.zip'
if (Test-Path -LiteralPath $output) { Remove-Item -LiteralPath $output }
$archive = [System.IO.Compression.ZipFile]::Open($output, [System.IO.Compression.ZipArchiveMode]::Create)
try {
    foreach ($file in $files) {
        [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($archive,
            (Join-Path $PSScriptRoot $file), $file, [System.IO.Compression.CompressionLevel]::Optimal) | Out-Null
    }
} finally { $archive.Dispose() }
Write-Output "Created $output"
