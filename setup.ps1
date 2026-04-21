# ============================================================
# Arogya AI — One-command setup script (Windows PowerShell)
# ============================================================
# Usage:  .\setup.ps1
# ============================================================

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   Arogya AI — Real-Time Multilingual Voice Agent  ║" -ForegroundColor Cyan
Write-Host "║              Setup Script (Windows)               ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ── 1. Check prerequisites ──────────────────────────────────
Write-Host "► Checking prerequisites..." -ForegroundColor Yellow

function Check-Command($cmd) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        Write-Host "  ✗ $cmd not found. Please install it first." -ForegroundColor Red
        exit 1
    }
    Write-Host "  ✓ $cmd found" -ForegroundColor Green
}

Check-Command "docker"
Check-Command "docker-compose"
Check-Command "node"
Check-Command "npm"
Check-Command "python"

Write-Host ""

# ── 2. Create .env from example ────────────────────────────
Write-Host "► Setting up environment variables..." -ForegroundColor Yellow

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "  ✓ Created .env from .env.example" -ForegroundColor Green
    Write-Host "  ⚠  IMPORTANT: Edit .env and add your OPENAI_API_KEY" -ForegroundColor Yellow
} else {
    Write-Host "  ✓ .env already exists" -ForegroundColor Green
}

Write-Host ""

# ── 3. Install frontend dependencies ───────────────────────
Write-Host "► Installing frontend dependencies..." -ForegroundColor Yellow

Set-Location frontend
npm install --silent
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ✗ npm install failed" -ForegroundColor Red
    exit 1
}
Write-Host "  ✓ Frontend dependencies installed" -ForegroundColor Green
Set-Location ..

Write-Host ""

# ── 4. Check Docker is running ─────────────────────────────
Write-Host "► Checking Docker daemon..." -ForegroundColor Yellow

$dockerInfo = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ✗ Docker is not running. Please start Docker Desktop." -ForegroundColor Red
    exit 1
}
Write-Host "  ✓ Docker is running" -ForegroundColor Green

Write-Host ""

# ── 5. Build and start services ────────────────────────────
Write-Host "► Building and starting Docker services..." -ForegroundColor Yellow
Write-Host "  (This may take a few minutes on first run)" -ForegroundColor Gray

docker-compose up --build -d

if ($LASTEXITCODE -ne 0) {
    Write-Host "  ✗ docker-compose failed" -ForegroundColor Red
    exit 1
}

Write-Host "  ✓ All services started" -ForegroundColor Green
Write-Host ""

# ── 6. Wait for services to be healthy ─────────────────────
Write-Host "► Waiting for services to be ready..." -ForegroundColor Yellow

$maxWait = 60
$waited = 0
$ready = $false

while ($waited -lt $maxWait) {
    Start-Sleep -Seconds 3
    $waited += 3

    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/api/health" -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            $ready = $true
            break
        }
    } catch {
        # Not ready yet
    }

    Write-Host "  Waiting... ($waited/$maxWait s)" -ForegroundColor Gray
}

if ($ready) {
    Write-Host "  ✓ Backend is healthy" -ForegroundColor Green
} else {
    Write-Host "  ⚠  Backend health check timed out (may still be starting)" -ForegroundColor Yellow
}

Write-Host ""

# ── 7. Summary ─────────────────────────────────────────────
Write-Host "╔══════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║                  Setup Complete!                  ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "  Frontend:   http://localhost:3000" -ForegroundColor Cyan
Write-Host "  Backend:    http://localhost:8000" -ForegroundColor Cyan
Write-Host "  API Docs:   http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "  Health:     http://localhost:8000/api/health" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Logs:       docker-compose logs -f" -ForegroundColor Gray
Write-Host "  Stop:       docker-compose down" -ForegroundColor Gray
Write-Host ""
Write-Host "  ⚠  Make sure OPENAI_API_KEY is set in .env" -ForegroundColor Yellow
Write-Host ""