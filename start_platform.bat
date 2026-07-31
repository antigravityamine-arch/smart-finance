@echo off
echo ==============================================
echo Starting Smart Finance Risk Platform
echo ==============================================
echo.
echo Step 1: Checking and installing dependencies...
py -m pip install -r requirements.txt
echo.
echo Step 2: Starting the server...
start cmd /k "title Flask Server && py app.py"

echo.
echo Waiting for server to start...
timeout /t 3 /nobreak >nul
start http://127.0.0.1:5050/logout
echo The platform should now be open in your browser.
echo.
echo If the app didn't open or showed an error, please read the messages above or in the new window.
pause
