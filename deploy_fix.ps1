# Quick fix script to ensure proper rename and deploy

cd c:\Users\hadao\OneDrive\Documents\Programming\amidata\ta-dashboard-deploy

# If ta_dashboard.py still exists, rename it
if (Test-Path "ta_dashboard.py") {
    Write-Host "Renaming ta_dashboard.py to macd_reversal_dashboard.py..."
    Move-Item -Force ta_dashboard.py macd_reversal_dashboard.py
}

# Stage the changes
git add -A

# Commit
git commit -m "Fix AttributeError: Add null check for current_tickers_df

- Added try-catch for tm.get_all_tickers()
- Check for None before accessing .empty
- Graceful error handling if ticker manager fails"

# Push to GitHub
git push origin main

Write-Host "`nDeployed! Streamlit Cloud will auto-update in ~1 minute"
