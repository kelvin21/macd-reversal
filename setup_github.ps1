# First-time GitHub setup

Write-Host "Setting up GitHub remote..." -ForegroundColor Cyan

cd c:\Users\hadao\OneDrive\Documents\Programming\amidata\ta-dashboard-deploy

# Prompt for GitHub username and repo name
$username = Read-Host "Enter your GitHub username"
$reponame = Read-Host "Enter repository name (default: macd-reversal)"

if ([string]::IsNullOrWhiteSpace($reponame)) {
    $reponame = "macd-reversal"
}

$remoteUrl = "https://github.com/$username/$reponame.git"

Write-Host "`nAdding remote: $remoteUrl" -ForegroundColor Yellow

# Check if remote already exists
$existingRemote = git remote get-url origin 2>$null
if ($existingRemote) {
    Write-Host "Remote 'origin' already exists: $existingRemote" -ForegroundColor Yellow
    $replace = Read-Host "Replace it? (Y/N)"
    if ($replace -eq "Y" -or $replace -eq "y") {
        git remote remove origin
        git remote add origin $remoteUrl
        Write-Host "✓ Remote updated" -ForegroundColor Green
    }
} else {
    git remote add origin $remoteUrl
    Write-Host "✓ Remote added" -ForegroundColor Green
}

Write-Host "`nNow run: .\update_repo.ps1 to push changes" -ForegroundColor Cyan
