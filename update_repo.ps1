# Script to update Git repository with all changes

Write-Host "Updating Git Repository..." -ForegroundColor Cyan
Write-Host "=" * 50

cd c:\Users\hadao\OneDrive\Documents\Programming\amidata\ta-dashboard-deploy

# Check if git is initialized
if (-not (Test-Path ".git")) {
    Write-Host "Initializing Git repository..." -ForegroundColor Yellow
    git init
    git branch -M main
}

# Check current status
Write-Host "`nCurrent Git Status:" -ForegroundColor Cyan
git status

# Rename ta_dashboard.py if it still exists
if (Test-Path "ta_dashboard.py") {
    Write-Host "`nRenaming ta_dashboard.py to macd_reversal_dashboard.py..." -ForegroundColor Yellow
    git mv ta_dashboard.py macd_reversal_dashboard.py 2>$null
    if ($LASTEXITCODE -ne 0) {
        # If git mv fails, do regular rename
        Move-Item -Force ta_dashboard.py macd_reversal_dashboard.py
        git add macd_reversal_dashboard.py
        git rm ta_dashboard.py 2>$null
    }
}

# Add all changes
Write-Host "`nStaging all changes..." -ForegroundColor Yellow
git add -A

# Show what will be committed
Write-Host "`nFiles to be committed:" -ForegroundColor Cyan
git status --short

# Create comprehensive commit message
$commitMessage = @"
Update MACD Reversal Dashboard

Major changes:
- Renamed ta_dashboard.py to macd_reversal_dashboard.py
- Fixed AttributeError with null check for current_tickers_df
- Updated all references in scripts (run.ps1, run.sh, Dockerfile)
- Updated documentation (README, QUICKSTART, INSTALLATION, DEPLOYMENT)
- Fixed ami2py_export_csv.py string formatting
- Optimized for Streamlit Cloud deployment
- Python-first approach (Docker optional)
- Added comprehensive error handling
- Improved ticker management admin panel

Configuration:
- Environment variable support
- Optional build_price_db module
- Docker Compose V2 compatibility
- Streamlit Cloud ready

Documentation:
- Complete installation guide
- Deployment instructions for multiple platforms
- Ticker management guide
- Quick start reference
"@

# Commit changes
Write-Host "`nCommitting changes..." -ForegroundColor Yellow
git commit -m $commitMessage

if ($LASTEXITCODE -ne 0) {
    Write-Host "No changes to commit or commit failed" -ForegroundColor Yellow
} else {
    Write-Host "✓ Changes committed successfully" -ForegroundColor Green
}

# Check if remote exists
$hasRemote = git remote -v 2>$null
if (-not $hasRemote) {
    Write-Host "`nNo remote repository configured." -ForegroundColor Yellow
    Write-Host "To add a remote, run:" -ForegroundColor Cyan
    Write-Host "  git remote add origin https://github.com/YOUR-USERNAME/macd-reversal.git" -ForegroundColor Gray
    Write-Host "`nThen push with:" -ForegroundColor Cyan
    Write-Host "  git push -u origin main" -ForegroundColor Gray
} else {
    # Push to remote
    Write-Host "`nPushing to remote repository..." -ForegroundColor Yellow
    git push origin main
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "`n✓ Successfully pushed to GitHub!" -ForegroundColor Green
        Write-Host "`nStreamlit Cloud will auto-deploy in ~1-2 minutes" -ForegroundColor Cyan
    } else {
        Write-Host "`n✗ Push failed. Check your credentials or network." -ForegroundColor Red
        Write-Host "`nIf this is the first push, run:" -ForegroundColor Yellow
        Write-Host "  git push -u origin main" -ForegroundColor Gray
    }
}

Write-Host "`nRepository updated!" -ForegroundColor Green
