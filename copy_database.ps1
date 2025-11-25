# Copy database from parent amidata directory

Write-Host "Copying database files..." -ForegroundColor Cyan

cd c:\Users\hadao\OneDrive\Documents\Programming\amidata\ta-dashboard-deploy

# Create data directory if it doesn't exist
New-Item -ItemType Directory -Force -Path "data" | Out-Null

# Source paths (adjust if needed)
$source_dir = "c:\Users\hadao\OneDrive\Documents\Programming\amidata"
$price_db = Join-Path $source_dir "price_data.db"
$analysis_db = Join-Path $source_dir "analysis_results.db"

# Copy price_data.db
if (Test-Path $price_db) {
    Write-Host "Copying price_data.db..." -ForegroundColor Yellow
    Copy-Item $price_db "data\price_data.db" -Force
    $size = (Get-Item "data\price_data.db").Length / 1MB
    Write-Host "✓ Copied price_data.db ($([math]::Round($size, 2)) MB)" -ForegroundColor Green
} else {
    Write-Host "⚠ price_data.db not found at: $price_db" -ForegroundColor Red
}

# Copy analysis_results.db (optional reference DB)
if (Test-Path $analysis_db) {
    Write-Host "Copying analysis_results.db..." -ForegroundColor Yellow
    Copy-Item $analysis_db "data\analysis_results.db" -Force
    $ref_size = (Get-Item "data\analysis_results.db").Length / 1MB
    Write-Host "✓ Copied analysis_results.db ($([math]::Round($ref_size, 2)) MB)" -ForegroundColor Green
} else {
    Write-Host "ℹ analysis_results.db not found (optional)" -ForegroundColor Yellow
}

Write-Host "`n✓ Database files copied to data\" -ForegroundColor Green
Write-Host "`nNext step: Run .\setup_git_lfs.ps1 to configure Git LFS" -ForegroundColor Cyan
