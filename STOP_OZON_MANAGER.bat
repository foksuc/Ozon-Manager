@echo off
setlocal
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8501" ^| findstr "LISTENING"') do (
    taskkill /PID %%a /F >nul 2>&1
)
echo Ozon Manager stopped.
timeout /t 2 >nul
