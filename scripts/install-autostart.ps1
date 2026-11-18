[CmdletBinding()]
param([string]$Python = "")

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$TaskName = "NixLMs User Runtime"
if ([string]::IsNullOrWhiteSpace($Python)) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCommand) { throw "Python 3.10+ não foi encontrado." }
    $Python = $pythonCommand.Source
}
$versionText = & $Python -c "import sys; print('%d.%d' % sys.version_info[:2])"
if ($LASTEXITCODE -ne 0) { throw "Não foi possível executar Python: $Python" }
$version = [version]$versionText
if ($version -lt [version]"3.10") { throw "NixLMs requer Python 3.10+. Encontrado: $version" }
$action = New-ScheduledTaskAction -Execute $Python -Argument "-m nixlms_web.server" -WorkingDirectory $RepoRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description "Inicia a interface local e o runtime autônomo governado da NixLMs no login do usuário." -Force | Out-Null
Write-Host "Inicialização configurada para este usuário."
Write-Host "Tarefa: $TaskName"
Write-Host "Projeto: $RepoRoot"
Write-Host "Interface: http://127.0.0.1:8765"
Write-Host "Para remover: .\scripts\remove-autostart.ps1"
