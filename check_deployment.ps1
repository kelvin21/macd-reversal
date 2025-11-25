# Check deployment configuration

Write-Host "Checking Streamlit Cloud Deployment..." -ForegroundColor Cyan
Write-Host "=" * 50

cd c:\Users\hadao\OneDrive\Documents\Programming\amidata\ta-dashboard-deploy

# Check required files
Write-Host "`nRequired Files:" -ForegroundColor Yellow
$required_files = @(
    "macd_reversal_dashboard.py",
    "requirements.txt",
    "ticker_manager.py"
)

foreach ($file in $required_files) {
    if (Test-Path $file) {
        Write-Host "  ✓ $file" -ForegroundColor Green
    } else {
        Write-Host "  ✗ $file (MISSING!)" -ForegroundColor Red
    }
}

# Check .streamlit directory
Write-Host "`nStreamlit Config:" -ForegroundColor Yellow
if (Test-Path ".streamlit") {
    Write-Host "  ✓ .streamlit directory exists" -ForegroundColor Green
    if (Test-Path ".streamlit\config.toml") {
        Write-Host "  ✓ config.toml exists" -ForegroundColor Green
    } else {
        Write-Host "  ⚠ config.toml missing (creating...)" -ForegroundColor Yellow
        New-Item -ItemType Directory -Force -Path ".streamlit" | Out-Null
        @"
[server]
headless = true
port = 8501
enableCORS = false

[browser]
gatherUsageStats = false
"@ | Out-File -FilePath ".streamlit\config.toml" -Encoding utf8
        Write-Host "  ✓ Created config.toml" -ForegroundColor Green
    }
} else {
    Write-Host "  ⚠ .streamlit directory missing (creating...)" -ForegroundColor Yellow
    New-Item -ItemType Directory -Force -Path ".streamlit" | Out-Null
    @"
[server]
headless = true
port = 8501
enableCORS = false

[browser]
gatherUsageStats = false
"@ | Out-File -FilePath ".streamlit\config.toml" -Encoding utf8
    Write-Host "  ✓ Created .streamlit\config.toml" -ForegroundColor Green
}

# Check data directory
Write-Host "`nData Directory:" -ForegroundColor Yellow
if (Test-Path "data") {
    Write-Host "  ✓ data directory exists" -ForegroundColor Green
    if (Test-Path "data\price_data.db") {
        $size = (Get-Item "data\price_data.db").Length
        Write-Host "  ✓ price_data.db exists (${size} bytes)" -ForegroundColor Green
    } else {
        Write-Host "  ⚠ price_data.db missing" -ForegroundColor Yellow
    }
} else {
    Write-Host "  ⚠ data directory missing (creating...)" -ForegroundColor Yellow
    New-Item -ItemType Directory -Force -Path "data" | Out-Null
    Write-Host "  ✓ Created data directory" -ForegroundColor Green
}

# Check requirements.txt
Write-Host "`nDependencies (requirements.txt):" -ForegroundColor Yellow
if (Test-Path "requirements.txt") {
    Get-Content "requirements.txt" | ForEach-Object {
        Write-Host "  - $_" -ForegroundColor Gray
    }
} else {
    Write-Host "  ✗ requirements.txt missing!" -ForegroundColor Red
}

# Check Git status
Write-Host "`nGit Status:" -ForegroundColor Yellow
$gitStatus = git status --short 2>$null
if ($gitStatus) {
    Write-Host "  ⚠ Uncommitted changes:" -ForegroundColor Yellow
    git status --short | ForEach-Object {
        Write-Host "    $_" -ForegroundColor Gray
    }
    Write-Host "`n  Run: git add -A && git commit -m 'Fix deployment' && git push" -ForegroundColor Cyan
} else {
    Write-Host "  ✓ Working directory clean" -ForegroundColor Green
}

Write-Host "`nNext Steps:" -ForegroundColor Cyan
Write-Host "1. Commit and push changes: .\sync_and_push.ps1" -ForegroundColor Gray
Write-Host "2. Check Streamlit Cloud logs for errors" -ForegroundColor Gray
Write-Host "3. Verify main file path is: macd_reversal_dashboard.py" -ForegroundColor Gray
Write-Host "4. Check if database is being created on startup" -ForegroundColor Gray
