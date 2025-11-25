# Install and configure Git LFS for large database files

Write-Host "Setting up Git LFS for large database files..." -ForegroundColor Cyan
Write-Host "=" * 50

cd c:\Users\hadao\OneDrive\Documents\Programming\amidata\ta-dashboard-deploy

# Check if Git LFS is installed
$hasLFS = git lfs version 2>$null
if (-not $hasLFS) {
    Write-Host "`nGit LFS not installed. Installing..." -ForegroundColor Yellow
    Write-Host "Download from: https://git-lfs.github.com/" -ForegroundColor Cyan
    Write-Host "`nOr install via winget:" -ForegroundColor Cyan
    Write-Host "  winget install -e --id GitHub.GitLFS" -ForegroundColor Gray
    Write-Host "`nAfter installation, run this script again." -ForegroundColor Yellow
    exit 1
}

Write-Host "✓ Git LFS is installed" -ForegroundColor Green

# Initialize Git LFS in this repo
Write-Host "`nInitializing Git LFS..." -ForegroundColor Yellow
git lfs install

# Track database files
Write-Host "`nConfiguring Git LFS to track .db files..." -ForegroundColor Yellow
git lfs track "*.db"
git lfs track "data/*.db"

# Add .gitattributes
Write-Host "`nUpdating .gitattributes..." -ForegroundColor Yellow
git add .gitattributes

# Check if database exists
if (Test-Path "data\price_data.db") {
    $size = (Get-Item "data\price_data.db").Length / 1MB
    Write-Host "`n✓ Database found: data\price_data.db ($([math]::Round($size, 2)) MB)" -ForegroundColor Green
    
    # Stage the database
    Write-Host "`nStaging database file with Git LFS..." -ForegroundColor Yellow
    git add data/price_data.db
    
    Write-Host "`n✓ Database staged successfully" -ForegroundColor Green
} else {
    Write-Host "`n⚠ Database not found at data\price_data.db" -ForegroundColor Yellow
    Write-Host "Copy your database file to data\ directory" -ForegroundColor Yellow
}

# Commit
Write-Host "`nCommitting changes..." -ForegroundColor Yellow
$commitMsg = @"
Add database file with Git LFS

Configured Git LFS for .db files
Added price_data.db (~$([math]::Round($size, 2)) MB)
"@
git commit -m $commitMsg

Write-Host "`n✓ Ready to push!" -ForegroundColor Green
Write-Host "`nRun: git push origin main" -ForegroundColor Cyan
