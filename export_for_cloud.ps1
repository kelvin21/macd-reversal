# Export database as CSV for Streamlit Cloud upload

Write-Host "Exporting database to CSV for Streamlit Cloud..." -ForegroundColor Cyan

cd c:\Users\hadao\OneDrive\Documents\Programming\amidata

# Export last 365 days for all tickers in watchlist 0
python ami2py_export_csv.py --watchlist 0 --dates 365 --output cloud_export.csv

if ($LASTEXITCODE -eq 0) {
    $size = (Get-Item "cloud_export.csv").Length / 1MB
    $sizeRounded = [math]::Round($size, 2)
    Write-Host "`n*** CSV Export Complete ***" -ForegroundColor Green
    Write-Host "File: cloud_export.csv ($sizeRounded MB)" -ForegroundColor Gray
    Write-Host "`nNext steps:" -ForegroundColor Cyan
    Write-Host "  1. Deploy app to Streamlit Cloud (database will be created empty)" -ForegroundColor Gray
    Write-Host "  2. Open deployed app" -ForegroundColor Gray
    Write-Host "  3. Expand 'Admin: Manage Tickers' in sidebar" -ForegroundColor Gray
    Write-Host "  4. Upload cloud_export.csv via 'Bulk Import CSV'" -ForegroundColor Gray
} else {
    Write-Host "*** Export failed ***" -ForegroundColor Red
}
