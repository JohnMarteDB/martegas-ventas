<#
  Registers a Windows Scheduled Task that runs the nightly MarteGas update.
  Run once, in a normal (non-admin is fine) PowerShell:

      powershell -ExecutionPolicy Bypass -File scripts\setup_task.ps1

  Default time is 01:30 (after the midnight Gmail script drops the reports).
  Override with:  -At "02:15"
#>
param(
  [string]$At = "01:30",
  [string]$TaskName = "MarteGas Sales Update"
)

$ErrorActionPreference = "Stop"
$proj = Split-Path -Parent $PSScriptRoot
$bat  = Join-Path $proj "scripts\update.bat"

if (-not (Test-Path $bat)) { throw "update.bat not found at $bat" }

$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$bat`"" -WorkingDirectory $proj
$trigger = New-ScheduledTaskTrigger -Daily -At $At

# Run only when the user is logged on, so the Google Drive (G:) mount exists.
$principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited

$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun `
  -DontStopOnIdleEnd -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
  -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
  -Principal $principal -Settings $settings -Force | Out-Null

Write-Host "Registered scheduled task '$TaskName' to run daily at $At." -ForegroundColor Green
Write-Host "Test it now with:  Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "Remove it with:    Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
