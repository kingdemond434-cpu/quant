# Launch the unified dashboard (requires: pip install -r requirements-deploy.txt).
# Usage: .\scripts\launch_dashboard.ps1 [-Db data\sor_demo.sqlite]
param([string]$Db = "data\sor_demo.sqlite")
& .\.venv\Scripts\streamlit.exe run app\dashboard_app.py -- --db $Db
