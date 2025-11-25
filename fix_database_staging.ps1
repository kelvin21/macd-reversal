# Diagnose and fix database staging issues

Write-Host "Diagnosing database staging issue..." -ForegroundColor Cyan
Write-Host ("=" * 50)

cd c:\Users\hadao\OneDrive\Documents\Programming\amidata\ta-dashboard-deploy

# Step 1: Check if data directory exists
Write-Host "`nStep 1: Checking data directory..." -ForegroundColor Yellow
if (Test-Path "data") {
    Write-Host "  * data/ directory exists" -ForegroundColor Green
    $files = Get-ChildItem "data" -ErrorAction SilentlyContinue
    if ($files) {
        Write-Host "  * Files in data/:" -ForegroundColor Gray
        $files | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }
    } else {
        Write-Host "  * data/ directory is empty" -ForegroundColor Yellow
    }
} else {
    Write-Host "  * data/ directory does NOT exist - creating..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Path "data" -Force | Out-Null
    Write-Host "  * Created data/ directory" -ForegroundColor Green
}

# Step 2: Check if database file exists
Write-Host "`nStep 2: Checking database file..." -ForegroundColor Yellow
$dbPath = "data\price_data.db"
if (Test-Path $dbPath) {
    $size = (Get-Item $dbPath).Length / 1MB
    $sizeRounded = [math]::Round($size, 2)
    Write-Host "  * Database EXISTS: $sizeRounded MB" -ForegroundColor Green
} else {
    Write-Host "  * Database NOT FOUND at: $dbPath" -ForegroundColor Red
    
    # Try to find it in parent directory
    $parentDb = "..\price_data.db"
    if (Test-Path $parentDb) {
        Write-Host "  * Found in parent directory - copying..." -ForegroundColor Yellow
        Copy-Item $parentDb $dbPath -Force
        Write-Host "  * Database copied successfully" -ForegroundColor Green
    } else {
        Write-Host "  * Database not found anywhere" -ForegroundColor Red
        Write-Host "`nPlease specify the database location:" -ForegroundColor Yellow
        $customPath = Read-Host "Enter full path to price_data.db (or press Enter to skip)"
        
        if ($customPath -and (Test-Path $customPath)) {
            Copy-Item $customPath $dbPath -Force
            Write-Host "  * Database copied from custom location" -ForegroundColor Green
        } else {
            Write-Host "`n*** CANNOT PROCEED WITHOUT DATABASE ***" -ForegroundColor Red
            Write-Host "`nOptions:" -ForegroundColor Cyan
            Write-Host "  1. Copy database manually to: $dbPath" -ForegroundColor Gray
            Write-Host "  2. Use CSV export instead: python ami2py_export_csv.py --watchlist 0 --output cloud_export.csv" -ForegroundColor Gray
            exit 1
        }
    }
}

# Step 3: Check .gitignore
Write-Host "`nStep 3: Checking .gitignore..." -ForegroundColor Yellow
if (Test-Path ".gitignore") {
    $gitignoreContent = Get-Content ".gitignore" -Raw
    if ($gitignoreContent -match "^\*\.db" -or $gitignoreContent -match "^data/" -or $gitignoreContent -match "price_data\.db") {
        Write-Host "  * WARNING: .gitignore is blocking .db files!" -ForegroundColor Red
        Write-Host "  * Removing .db exclusions from .gitignore..." -ForegroundColor Yellow
        
        # Remove lines that block .db files
        $newContent = Get-Content ".gitignore" | Where-Object {
            $_ -notmatch "^\*\.db" -and 
            $_ -notmatch "^data/" -and 
            $_ -notmatch "price_data\.db" -and
            $_ -notmatch "\.db$"
        }
        $newContent | Set-Content ".gitignore"
        Write-Host "  * .gitignore updated" -ForegroundColor Green
    } else {
        Write-Host "  * .gitignore OK (not blocking .db files)" -ForegroundColor Green
    }
} else {
    Write-Host "  * No .gitignore file" -ForegroundColor Gray
}

# Step 4: Check Git status
Write-Host "`nStep 4: Checking Git status..." -ForegroundColor Yellow
$gitStatus = git status --porcelain $dbPath 2>&1
Write-Host "  Git status output: $gitStatus" -ForegroundColor Gray

# Step 5: Force add the database
Write-Host "`nStep 5: Force adding database to Git..." -ForegroundColor Yellow
git add -f $dbPath 2>&1 | Out-String | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }

if ($LASTEXITCODE -eq 0) {
    Write-Host "  * Database staged successfully!" -ForegroundColor Green
} else {
    Write-Host "  * Still failed to stage" -ForegroundColor Red
    Write-Host "`nTrying alternative method..." -ForegroundColor Yellow
    
    # Try with forward slash
    git add -f "data/price_data.db" 2>&1 | Out-String | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  * Success with forward slash path!" -ForegroundColor Green
    } else {
        Write-Host "  * All methods failed" -ForegroundColor Red
    }
}

# Step 6: Verify staging
Write-Host "`nStep 6: Verifying staged files..." -ForegroundColor Yellow
$staged = git diff --cached --name-only
if ($staged -match "price_data.db") {
    Write-Host "  * Database is now staged!" -ForegroundColor Green
    Write-Host "`nStaged files:" -ForegroundColor Cyan
    $staged | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
} else {
    Write-Host "  * Database still not staged" -ForegroundColor Red
    Write-Host "`nCurrent staged files:" -ForegroundColor Yellow
    if ($staged) {
        $staged | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
    } else {
        Write-Host "  (none)" -ForegroundColor Gray
    }
}

# Step 7: Recommendations
Write-Host "`nNext Steps:" -ForegroundColor Cyan
if ($staged -match "price_data.db") {
    Write-Host "  1. Commit: git commit -m 'Add database file'" -ForegroundColor Gray
    Write-Host "  2. Push: git push origin main" -ForegroundColor Gray
} else {
    Write-Host "  Database could not be staged. Consider alternatives:" -ForegroundColor Yellow
    Write-Host "  1. Export to CSV: cd .. && python ami2py_export_csv.py --watchlist 0 --output cloud_export.csv" -ForegroundColor Gray
    Write-Host "  2. Upload CSV via Streamlit Cloud dashboard admin panel" -ForegroundColor Gray
}

Write-Host "`nDone!" -ForegroundColor Green
