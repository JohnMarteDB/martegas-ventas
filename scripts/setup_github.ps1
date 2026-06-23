<#
  One-time GitHub Pages setup for the MarteGas dashboard.

  Prereqs: a free GitHub account. If you have the GitHub CLI ("gh") installed
  and logged in, this script does everything automatically. Otherwise it prints
  the manual steps.

  Usage:
      powershell -ExecutionPolicy Bypass -File scripts\setup_github.ps1 -Repo "martegas-ventas"
#>
param(
  [string]$Repo = "martegas-ventas",
  [string]$Visibility = "public"   # GitHub Pages is free only for public repos
)
$ErrorActionPreference = "Stop"
$proj = Split-Path -Parent $PSScriptRoot
Set-Location $proj

if (-not (Test-Path (Join-Path $proj ".git"))) {
  git init | Out-Null
  git add -A
  git commit -m "Sistema de ventas MarteGas: pipeline + dashboard" | Out-Null
  Write-Host "Initialized git repo." -ForegroundColor Green
}

# Ensure the default branch is 'main'
git branch -M main

$gh = Get-Command gh -ErrorAction SilentlyContinue
if ($gh) {
  Write-Host "GitHub CLI found - creating repo and enabling Pages..." -ForegroundColor Green
  gh repo create $Repo --$Visibility --source "." --remote origin --push
  # Enable Pages from the /docs folder on main
  $owner = (gh api user --jq ".login")
  gh api -X POST "repos/$owner/$Repo/pages" -f "source[branch]=main" -f "source[path]=/docs" 2>$null
  Write-Host ""
  Write-Host "Done. Your dashboard will be live in ~1-2 minutes at:" -ForegroundColor Green
  Write-Host "    https://$owner.github.io/$Repo/" -ForegroundColor Cyan
} else {
  Write-Host "GitHub CLI ('gh') not found. Do these steps once, manually:" -ForegroundColor Yellow
  Write-Host "  1. Create a new EMPTY repo at https://github.com/new  (name: $Repo, $Visibility)."
  Write-Host "  2. Back here, run:"
  Write-Host "         git remote add origin https://github.com/<your-user>/$Repo.git"
  Write-Host "         git push -u origin main"
  Write-Host "  3. On GitHub: Settings -> Pages -> Source = 'Deploy from a branch',"
  Write-Host "     Branch = 'main', Folder = '/docs', Save."
  Write-Host "  4. Your site appears at https://<your-user>.github.io/$Repo/"
  Write-Host ""
  Write-Host "Tip: install gh (https://cli.github.com) to automate this next time."
}
