# Complete workflow to push database to GitHub with Git LFS

Write-Host "Pushing database to GitHub with Git LFS..." -ForegroundColor Cyan
Write-Host ("=" * 50)

cd c:\Users\hadao\OneDrive\Documents\Programming\amidata\ta-dashboard-deploy

# Step 1: Copy database if needed
if (-not (Test-Path "data\price_data.db")) {
    Write-Host "`nStep 1: Copying database..." -ForegroundColor Yellow
    $source_db = "c:\Users\hadao\OneDrive\Documents\Programming\amidata\price_data.db"
    
    if (Test-Path $source_db) {
        New-Item -ItemType Directory -Force -Path "data" | Out-Null
        Copy-Item $source_db "data\price_data.db" -Force
        $size = (Get-Item "data\price_data.db").Length / 1MB
        $sizeRounded = [math]::Round($size, 2)
        Write-Host "  * Copied database ($sizeRounded MB)" -ForegroundColor Green
    } else {
        Write-Host "  * Database not found at: $source_db" -ForegroundColor Red
        exit 1
    }
} else {
    $size = (Get-Item "data\price_data.db").Length / 1MB
    $sizeRounded = [math]::Round($size, 2)
    Write-Host "`n* Database already exists ($sizeRounded MB)" -ForegroundColor Green
}

# Step 2: Check Git LFS
Write-Host "`nStep 2: Checking Git LFS..." -ForegroundColor Yellow
$hasLFS = git lfs version 2>$null
if (-not $hasLFS) {
    Write-Host "  * Git LFS not installed" -ForegroundColor Red
    Write-Host "`nInstall with:" -ForegroundColor Cyan
    Write-Host "  winget install -e --id GitHub.GitLFS" -ForegroundColor Gray
    Write-Host "Or download from: https://git-lfs.github.com/" -ForegroundColor Gray
    exit 1
}
Write-Host "  * Git LFS installed" -ForegroundColor Green

# Step 3: Configure Git LFS
Write-Host "`nStep 3: Configuring Git LFS..." -ForegroundColor Yellow
git lfs install
git lfs track "*.db"
git lfs track "data/*.db"
Write-Host "  * Configured to track .db files" -ForegroundColor Green

# Step 4: Stage files
Write-Host "`nStep 4: Staging files..." -ForegroundColor Yellow
git add .gitattributes
git add data/price_data.db
Write-Host "  * Files staged" -ForegroundColor Green

# Step 5: Commit
Write-Host "`nStep 5: Committing..." -ForegroundColor Yellow
$sizeMB = [math]::Round($size, 2)
$commitMsg = "Add database file with Git LFS - size: $sizeMB MB"
git commit -m $commitMsg
Write-Host "  * Changes committed" -ForegroundColor Green

# Step 6: Push
Write-Host "`nStep 6: Pushing to GitHub..." -ForegroundColor Yellow
Write-Host "  This may take a while for large files..." -ForegroundColor Gray
git push origin main

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n* Database pushed successfully!" -ForegroundColor Green
    Write-Host "`nStreamlit Cloud will have the database after next deploy" -ForegroundColor Cyan
} else {
    Write-Host "`n* Push failed" -ForegroundColor Red
    Write-Host "`nTroubleshooting:" -ForegroundColor Yellow
    Write-Host "  1. Check if you need to authenticate (use Personal Access Token)" -ForegroundColor Gray
    Write-Host "  2. Ensure Git LFS is properly configured" -ForegroundColor Gray
    Write-Host "  3. Check if GitHub LFS storage limit is reached" -ForegroundColor Gray
}
