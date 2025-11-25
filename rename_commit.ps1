# Run these commands to rename and commit changes

cd c:\Users\hadao\OneDrive\Documents\Programming\amidata\ta-dashboard-deploy

# Rename the main file
git mv ta_dashboard.py macd_reversal_dashboard.py

# Stage all updated references
git add run.ps1 run.sh Dockerfile README.md QUICKSTART.md docs/

# Commit the rename
git commit -m "Rename ta_dashboard to macd_reversal_dashboard

- Renamed main file to macd_reversal_dashboard.py
- Updated all script references (run.ps1, run.sh)
- Updated Docker configuration
- Updated documentation (README, QUICKSTART, INSTALLATION, DEPLOYMENT)"

# Push to GitHub
git push origin main
