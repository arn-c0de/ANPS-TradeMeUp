@echo off
echo ========================================
echo Fixing Dash Asset Loading Issues
echo ========================================
echo.

echo [1/3] Uninstalling Dash components...
pip uninstall -y dash dash-core-components dash-html-components dash-table dash-bootstrap-components

echo.
echo [2/3] Clearing pip cache...
pip cache purge

echo.
echo [3/3] Reinstalling Dash components...
pip install dash==3.4.0 dash-bootstrap-components==2.0.4

echo.
echo ========================================
echo Done! Please restart the dashboard.
echo ========================================
pause
