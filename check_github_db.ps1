# Check if database exists in local repo and GitHub

Write-Host "Checking database status..." -ForegroundColor Cyan
Write-Host ("=" * 50)

cd c:\Users\hadao\OneDrive\Documents\Programming\amidata\ta-dashboard-deploy

# Check local database
Write-Host "`nLocal Database:" -ForegroundColor Yellow
if (Test-Path "data\price_data.db") {
    $size = (Get-Item "data\price_data.db").Length / 1MB
    $sizeRounded = [math]::Round($size, 2)
    Write-Host "  * EXISTS: data\price_data.db ($sizeRounded MB)" -ForegroundColor Green
} else {
    Write-Host "  * NOT FOUND: data\price_data.db" -ForegroundColor Red
}

# Check if Git LFS is tracking the file
Write-Host "`nGit LFS Status:" -ForegroundColor Yellow
$lfsFiles = git lfs ls-files 2>$null
if ($lfsFiles) {
    Write-Host "  * Git LFS is tracking:" -ForegroundColor Green
    $lfsFiles | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }
} else {
    Write-Host "  * Git LFS not configured or no files tracked" -ForegroundColor Yellow
}

# Check if file is staged/committed
Write-Host "`nGit Status:" -ForegroundColor Yellow
$gitStatus = git status --porcelain data/price_data.db 2>$null
if ($gitStatus) {
    Write-Host "  * Database has uncommitted changes:" -ForegroundColor Yellow
    Write-Host "    $gitStatus" -ForegroundColor Gray
} else {
    Write-Host "  * Database is committed" -ForegroundColor Green
}

# Check last commit that touched the database
Write-Host "`nLast Commit with Database:" -ForegroundColor Yellow
$lastCommit = git log --oneline -1 -- data/price_data.db 2>$null
if ($lastCommit) {
    Write-Host "  $lastCommit" -ForegroundColor Gray
} else {
    Write-Host "  * Database never committed" -ForegroundColor Red
}

# Check remote URL
Write-Host "`nGitHub Repository:" -ForegroundColor Yellow
$remoteUrl = git remote get-url origin 2>$null
if ($remoteUrl) {
    Write-Host "  $remoteUrl" -ForegroundColor Gray
    
    # Extract repo info for GitHub URL
    if ($remoteUrl -match "github.com[:/](.+)/(.+).git") {
        $owner = $matches[1]
        $repo = $matches[2]
        $githubUrl = "https://github.com/$owner/$repo/blob/main/data/price_data.db"
        Write-Host "`n  Check on GitHub:" -ForegroundColor Cyan
        Write-Host "  $githubUrl" -ForegroundColor Gray
    }
} else {
    Write-Host "  * No remote configured" -ForegroundColor Red
}

# Recommendations
Write-Host "`nRecommendations:" -ForegroundColor Cyan
if (-not (Test-Path "data\price_data.db")) {
    Write-Host "  1. Copy database: .\copy_database.ps1" -ForegroundColor Yellow
} elseif (-not $lfsFiles) {
    Write-Host "  1. Setup Git LFS: git lfs install && git lfs track '*.db'" -ForegroundColor Yellow
} elseif ($gitStatus) {
    Write-Host "  1. Commit database: git add data/price_data.db && git commit -m 'Add database'" -ForegroundColor Yellow
} else {
    Write-Host "  1. Push to GitHub: git push origin main" -ForegroundColor Yellow
}

Write-Host "`nAlternative: Use CSV import on Streamlit Cloud" -ForegroundColor Cyan
Write-Host "  - Export CSV: python ami2py_export_csv.py --watchlist 0 --output cloud_export.csv" -ForegroundColor Gray
Write-Host "  - Upload via dashboard admin panel after deployment" -ForegroundColor Gray
