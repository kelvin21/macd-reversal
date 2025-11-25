# Add database to Git repository with proper Git LFS setup

Write-Host "Adding database to Git repository..." -ForegroundColor Cyan
Write-Host ("=" * 50)

cd c:\Users\hadao\OneDrive\Documents\Programming\amidata\ta-dashboard-deploy

# Step 1: Copy database if not exists
if (-not (Test-Path "data\price_data.db")) {
    Write-Host "`nStep 1: Copying database..." -ForegroundColor Yellow
    
    $source = "c:\Users\hadao\OneDrive\Documents\Programming\amidata\price_data.db"
    
    if (Test-Path $source) {
        New-Item -ItemType Directory -Force -Path "data" | Out-Null
        Copy-Item $source "data\price_data.db" -Force
        $size = (Get-Item "data\price_data.db").Length / 1MB
        $sizeRounded = [math]::Round($size, 2)
        Write-Host "  * Database copied: $sizeRounded MB" -ForegroundColor Green
    } else {
        Write-Host "  * ERROR: Database not found at $source" -ForegroundColor Red
        Write-Host "`nPlease specify the correct path to your price_data.db file" -ForegroundColor Yellow
        exit 1
    }
} else {
    $size = (Get-Item "data\price_data.db").Length / 1MB
    $sizeRounded = [math]::Round($size, 2)
    Write-Host "`nDatabase already exists: $sizeRounded MB" -ForegroundColor Green
}

# Step 2: Check database size and recommend approach
Write-Host "`nStep 2: Checking database size..." -ForegroundColor Yellow
if ($size -gt 100) {
    Write-Host "  * Database is large ($sizeRounded MB)" -ForegroundColor Yellow
    Write-Host "  * Git LFS required for files > 100MB" -ForegroundColor Cyan
    
    # Check if Git LFS is installed
    $hasLFS = git lfs version 2>$null
    if (-not $hasLFS) {
        Write-Host "`n  * ERROR: Git LFS not installed!" -ForegroundColor Red
        Write-Host "`n  Install Git LFS first:" -ForegroundColor Yellow
        Write-Host "    winget install -e --id GitHub.GitLFS" -ForegroundColor Gray
        Write-Host "    OR download from: https://git-lfs.github.com/" -ForegroundColor Gray
        Write-Host "`n  After installation, run this script again." -ForegroundColor Cyan
        exit 1
    }
    
    Write-Host "  * Git LFS is installed" -ForegroundColor Green
    
    # Configure Git LFS
    Write-Host "`nStep 3: Configuring Git LFS..." -ForegroundColor Yellow
    git lfs install
    git lfs track "*.db"
    git lfs track "data/*.db"
    Write-Host "  * Git LFS configured" -ForegroundColor Green
    
    # Stage .gitattributes
    git add .gitattributes
    
} else {
    Write-Host "  * Database size OK for regular Git ($sizeRounded MB)" -ForegroundColor Green
}

# Step 4: Stage database
Write-Host "`nStep 4: Staging database..." -ForegroundColor Yellow
git add data/price_data.db

if ($LASTEXITCODE -ne 0) {
    Write-Host "  * ERROR: Failed to stage database" -ForegroundColor Red
    exit 1
}
Write-Host "  * Database staged successfully" -ForegroundColor Green

# Step 5: Commit
Write-Host "`nStep 5: Committing..." -ForegroundColor Yellow
$commitMsg = "Add price_data.db database file - size: $sizeRounded MB"
git commit -m $commitMsg

if ($LASTEXITCODE -ne 0) {
    Write-Host "  * ERROR: Commit failed" -ForegroundColor Red
    git status
    exit 1
}
Write-Host "  * Committed successfully" -ForegroundColor Green

# Step 6: Show status before push
Write-Host "`nStep 6: Verifying commit..." -ForegroundColor Yellow
$lastCommit = git log --oneline -1 -- data/price_data.db
if ($lastCommit) {
    Write-Host "  * Last commit: $lastCommit" -ForegroundColor Green
} else {
    Write-Host "  * WARNING: Database not in last commit" -ForegroundColor Yellow
}

# Step 7: Push to GitHub
Write-Host "`nStep 7: Pushing to GitHub..." -ForegroundColor Yellow
Write-Host "  * This may take several minutes for large files..." -ForegroundColor Gray

git push origin main

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n*** SUCCESS ***" -ForegroundColor Green
    Write-Host "Database pushed to GitHub!" -ForegroundColor Green
    Write-Host "`nVerify on GitHub:" -ForegroundColor Cyan
    $remoteUrl = git remote get-url origin
    Write-Host "  $remoteUrl" -ForegroundColor Gray
    Write-Host "`nStreamlit Cloud will have the database on next deployment" -ForegroundColor Cyan
} else {
    Write-Host "`n*** PUSH FAILED ***" -ForegroundColor Red
    Write-Host "`nCommon issues:" -ForegroundColor Yellow
    Write-Host "  1. Authentication required - use Personal Access Token" -ForegroundColor Gray
    Write-Host "  2. GitHub LFS bandwidth limit reached (1GB/month free)" -ForegroundColor Gray
    Write-Host "  3. File too large even for LFS (max 2GB)" -ForegroundColor Gray
    Write-Host "`nAlternative: Export to CSV for cloud upload" -ForegroundColor Cyan
    Write-Host "  python ami2py_export_csv.py --watchlist 0 --output cloud_export.csv" -ForegroundColor Gray
}

Write-Host "`nDone!" -ForegroundColor Green
