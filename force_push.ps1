# Force push to remote (overwrites remote history - use with caution!)

Write-Host "⚠️  WARNING: Force Push" -ForegroundColor Red
Write-Host "This will OVERWRITE the remote repository with your local changes" -ForegroundColor Yellow
Write-Host "Any commits on GitHub that you don't have locally will be LOST" -ForegroundColor Yellow
Write-Host ""

$confirm = Read-Host "Are you sure? Type 'YES' to continue"

if ($confirm -eq "YES") {
    cd c:\Users\hadao\OneDrive\Documents\Programming\amidata\ta-dashboard-deploy
    
    Write-Host "`nForce pushing to GitHub..." -ForegroundColor Yellow
    git push origin main --force
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "`n✓ Force push successful" -ForegroundColor Green
        Write-Host "Streamlit Cloud will redeploy automatically" -ForegroundColor Cyan
    } else {
        Write-Host "`n✗ Force push failed" -ForegroundColor Red
    }
} else {
    Write-Host "`nCancelled" -ForegroundColor Yellow
}
