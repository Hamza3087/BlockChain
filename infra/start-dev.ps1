# ReplantWorld Development Environment Startup Script
# This script starts the complete development environment

Write-Host "🚀 Starting ReplantWorld Development Environment" -ForegroundColor Green
Write-Host "===============================================" -ForegroundColor Green

# Check if Docker is running
try {
    docker version | Out-Null
    Write-Host "✅ Docker is running" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker is not running. Please start Docker Desktop first." -ForegroundColor Red
    exit 1
}

# Navigate to infra directory
$infraPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $infraPath

Write-Host "`n📦 Starting Docker Compose services..." -ForegroundColor Yellow
Write-Host "This may take a few minutes on first run..." -ForegroundColor Gray

# Start Docker Compose services
docker-compose up -d

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Docker Compose services started successfully" -ForegroundColor Green
} else {
    Write-Host "❌ Failed to start Docker Compose services" -ForegroundColor Red
    exit 1
}

Write-Host "`n⏳ Waiting for services to be ready..." -ForegroundColor Yellow

# Wait for services to be ready
Start-Sleep -Seconds 10

# Check service health
Write-Host "`n🏥 Checking service health..." -ForegroundColor Yellow

$maxRetries = 30
$retryCount = 0
$allHealthy = $false

while ($retryCount -lt $maxRetries -and -not $allHealthy) {
    $retryCount++
    Write-Host "Health check attempt $retryCount/$maxRetries..." -ForegroundColor Gray
    
    try {
        # Check backend health
        $healthResponse = Invoke-WebRequest -Uri "http://localhost:8000/api/healthz/" -TimeoutSec 5 -UseBasicParsing
        $healthData = $healthResponse.Content | ConvertFrom-Json
        
        if ($healthData.status -eq "ok") {
            Write-Host "✅ All services are healthy!" -ForegroundColor Green
            $allHealthy = $true
            break
        } else {
            Write-Host "⚠️  Services are starting up... (Status: $($healthData.status))" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "⚠️  Services are still starting up..." -ForegroundColor Yellow
    }
    
    if ($retryCount -lt $maxRetries) {
        Start-Sleep -Seconds 5
    }
}

if (-not $allHealthy) {
    Write-Host "⚠️  Services may still be starting up. You can check manually." -ForegroundColor Yellow
}

Write-Host "`n🎉 Development environment is ready!" -ForegroundColor Green
Write-Host "====================================" -ForegroundColor Green

Write-Host "`n🔗 Access your applications:" -ForegroundColor Cyan
Write-Host "Frontend:     http://localhost:3000" -ForegroundColor Blue
Write-Host "Backend API:  http://localhost:8000" -ForegroundColor Blue
Write-Host "Health Check: http://localhost:8000/api/healthz/" -ForegroundColor Blue
Write-Host "Admin Panel:  http://localhost:8000/admin/" -ForegroundColor Blue

Write-Host "`n📊 View logs:" -ForegroundColor Cyan
Write-Host "All services: docker-compose logs -f" -ForegroundColor White
Write-Host "Backend only: docker-compose logs -f backend" -ForegroundColor White
Write-Host "Frontend only: docker-compose logs -f frontend" -ForegroundColor White

Write-Host "`n🛠️  Useful commands:" -ForegroundColor Cyan
Write-Host "Stop services:    docker-compose down" -ForegroundColor White
Write-Host "Restart services: docker-compose restart" -ForegroundColor White
Write-Host "View status:      docker-compose ps" -ForegroundColor White
Write-Host "Run tests:        .\test-setup.ps1" -ForegroundColor White

Write-Host "`n📝 Next steps:" -ForegroundColor Cyan
Write-Host "1. Run tests: .\test-setup.ps1" -ForegroundColor White
Write-Host "2. Set up Solana CLI: .\setup-solana.ps1" -ForegroundColor White
Write-Host "3. Create superuser: docker-compose exec backend python manage.py createsuperuser" -ForegroundColor White
Write-Host "4. Start building your carbon credit NFT platform! 🌱" -ForegroundColor White

Write-Host "`n💡 Tip: Keep this terminal open to see any startup messages." -ForegroundColor Yellow
