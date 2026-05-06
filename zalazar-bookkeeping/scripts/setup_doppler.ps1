# setup_doppler.ps1
# Helper script to sync secrets from Doppler for production readiness

param (
    [string]$Project = "zalazar-bookkeeping",
    [string]$Config = "prd"
)

Write-Host "Syncing secrets from Doppler for project: $Project, config: $Config..." -ForegroundColor Gold

if (!(Get-Command doppler -ErrorAction SilentlyContinue)) {
    Write-Error "Doppler CLI is not installed. Please install it from https://docs.doppler.com/docs/install-cli"
    return
}

# Login check
$loginCheck = doppler me 2>&1
if ($loginCheck -match "not logged in") {
    Write-Host "Not logged in. Running 'doppler login'..."
    doppler login
}

# Pull secrets into .env.production
doppler secrets download --project $Project --config $Config --format env --no-confirm --filepath .env.production

if ($LASTEXITCODE -eq 0) {
    Write-Host "Success! .env.production has been updated." -ForegroundColor Green
    Write-Host "IMPORTANT: Never commit .env.production to version control." -ForegroundColor Yellow
} else {
    Write-Error "Failed to download secrets from Doppler."
}
