# Zalazar Bookkeeping Startup Script
Write-Host "🚀 Starting Zalazar Bookkeeping System..." -ForegroundColor Cyan

# Start Backend
Write-Host "Starting Backend API on http://localhost:8000..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd zalazar-bookkeeping; `$env:PYTHONPATH='.;src'; uvicorn services.api.main:app --reload --port 8000"

# Start Frontend
Write-Host "Starting Frontend Dashboard on http://localhost:5173..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd zalazar-bookkeeping/frontend; npm run dev"

Write-Host "✅ Both processes are starting in new windows." -ForegroundColor Yellow
Write-Host "Visit http://localhost:5173 in your browser." -ForegroundColor Cyan
