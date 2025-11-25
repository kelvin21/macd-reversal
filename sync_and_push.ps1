# Sync with remote and push changes

Write-Host "Syncing with GitHub..." -ForegroundColor Cyan
Write-Host "=" * 50

cd c:\Users\hadao\OneDrive\Documents\Programming\amidata\ta-dashboard-deploy

# Pull latest changes from remote
Write-Host "`nPulling latest changes from remote..." -ForegroundColor Yellow
git pull origin main --rebase

if ($LASTEXITCODE -ne 0) {
    Write-Host "`n⚠ Pull failed or has conflicts" -ForegroundColor Red
    Write-Host "`nTrying merge strategy instead..." -ForegroundColor Yellow
    git pull origin main --no-rebase
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "`n✗ Merge conflicts detected!" -ForegroundColor Red
        Write-Host "`nOptions:" -ForegroundColor Yellow
        Write-Host "1. Resolve conflicts manually, then run:" -ForegroundColor Gray
        Write-Host "   git add ." -ForegroundColor Cyan
        Write-Host "   git commit -m 'Resolved merge conflicts'" -ForegroundColor Cyan
        Write-Host "   git push origin main" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "2. Force push (DANGEROUS - overwrites remote):" -ForegroundColor Gray
        Write-Host "   git push origin main --force" -ForegroundColor Cyan
        exit 1
    }
}

Write-Host "`n✓ Successfully pulled remote changes" -ForegroundColor Green

# Check if there are changes to push
$status = git status --porcelain
if ([string]::IsNullOrWhiteSpace($status)) {
    Write-Host "`nNo local changes to push" -ForegroundColor Yellow
} else {
    Write-Host "`nLocal changes detected, staging..." -ForegroundColor Yellow
    git add -A
    git commit -m "Merge local changes with remote"
}

# Push to remote
Write-Host "`nPushing to GitHub..." -ForegroundColor Yellow
git push origin main

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✓ Successfully pushed to GitHub!" -ForegroundColor Green
    Write-Host "`nStreamlit Cloud will auto-deploy in ~1-2 minutes" -ForegroundColor Cyan
    Write-Host "Visit: https://github.com/kelvin21/macd-reversal" -ForegroundColor Cyan
} else {
    Write-Host "`n✗ Push failed" -ForegroundColor Red
    Write-Host "Check your credentials or network connection" -ForegroundColor Yellow
}

Write-Host "`nDone!" -ForegroundColor Green
