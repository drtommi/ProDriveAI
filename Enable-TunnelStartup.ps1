[CmdletBinding()]
param([switch]$StartSaved)

$ErrorActionPreference = 'Stop'
$settingsDir = Join-Path $env:LOCALAPPDATA 'ProDriveAI'
$settingsFile = Join-Path $settingsDir 'tunnel-settings.xml'
$installedScript = Join-Path $settingsDir 'Enable-TunnelStartup.ps1'

function Start-SavedTunnel {
    $settings = Import-Clixml -LiteralPath $settingsFile
    $env:CONTROL_PLANE_API_KEY = [System.Net.NetworkCredential]::new('', $settings.Key).Password
    foreach ($entry in $settings.ServerEnvironment.GetEnumerator()) {
        [Environment]::SetEnvironmentVariable($entry.Key, $entry.Value, 'Process')
    }
    Start-Process -FilePath $settings.Client -ArgumentList 'run', '--profile', 'prodriveai' -WindowStyle Hidden
}

if ($StartSaved) {
    Start-SavedTunnel
    return
}

$client = (Get-Command tunnel-client.exe -CommandType Application).Source
$serverEnv = @{}
foreach ($name in 'DRIVE_CLI', 'APPROVAL_PYTHON', 'PRODRIVEAI_PYTHON') {
    $path = [Environment]::GetEnvironmentVariable($name)
    if (!$path -or !(Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Set $name in the PowerShell window you use for the working tunnel, then run setup there."
    }
    $serverEnv[$name] = $path
}
$serverEnv['DRIVE_ALLOW_CREATE'] = if ($env:DRIVE_ALLOW_CREATE -eq '1') { '1' } else { '0' }
$serverEnv['DRIVE_ALLOW_MANAGE'] = if ($env:DRIVE_ALLOW_MANAGE -eq '1') { '1' } else { '0' }
foreach ($name in 'DRIVE_MAX_FILE_MB', 'PRODRIVEAI_OCR_LANG') {
    $value = [Environment]::GetEnvironmentVariable($name)
    if ($value) { $serverEnv[$name] = $value }
}

$key = if ($env:CONTROL_PLANE_API_KEY) {
    ConvertTo-SecureString $env:CONTROL_PLANE_API_KEY -AsPlainText -Force
} else {
    Read-Host 'Paste your OpenAI tunnel runtime key' -AsSecureString
}
if (!$key.Length) { throw 'Setup needs a tunnel runtime key.' }

$null = New-Item -ItemType Directory -Path $settingsDir -Force
$settings = [pscustomobject]@{ Client = $client; Key = $key; ServerEnvironment = $serverEnv }
$settings | Export-Clixml -LiteralPath $settingsFile
if ($PSCommandPath -ne $installedScript) {
    Copy-Item -LiteralPath $PSCommandPath -Destination $installedScript -Force
}
$startup = [Environment]::GetFolderPath('Startup')
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut((Join-Path $startup 'ProDriveAI Tunnel.lnk'))
$shortcut.TargetPath = (Get-Command powershell.exe -CommandType Application).Source
$shortcut.Arguments = '-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy RemoteSigned -File "' + $installedScript + '" -StartSaved'
$shortcut.WindowStyle = 7
$shortcut.Save()
Write-Output 'ProDriveAI Tunnel is configured to start at Windows sign-in.'
Start-SavedTunnel
Write-Output 'Started the tunnel in the background. Check it with: tunnel-client health --port 8080 --require-control-plane-poll'
