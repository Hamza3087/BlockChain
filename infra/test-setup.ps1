# ReplantWorld Development Environment Test Script
# This script validates that all components are working correctly

Write-Host "🚀 Testing ReplantWorld Development Environment" -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Green

$testResults = @()

# Function to test HTTP endpoint
function Test-Endpoint {
    param(
        [string]$Name,
        [string]$Url,
        [int]$ExpectedStatus = 200,
        [int]$TimeoutSeconds = 10
    )
    
    try {
        Write-Host "Testing $Name..." -ForegroundColor Yellow
        $response = Invoke-WebRequest -Uri $Url -TimeoutSec $TimeoutSeconds -UseBasicParsing
        
        if ($response.StatusCode -eq $ExpectedStatus) {
            Write-Host "✅ $Name - OK (Status: $($response.StatusCode))" -ForegroundColor Green
            return @{ Name = $Name; Status = "PASS"; Details = "Status: $($response.StatusCode)" }
        } else {
            Write-Host "❌ $Name - FAIL (Expected: $ExpectedStatus, Got: $($response.StatusCode))" -ForegroundColor Red
            return @{ Name = $Name; Status = "FAIL"; Details = "Expected: $ExpectedStatus, Got: $($response.StatusCode)" }
        }
    } catch {
        Write-Host "❌ $Name - FAIL (Error: $($_.Exception.Message))" -ForegroundColor Red
        return @{ Name = $Name; Status = "FAIL"; Details = $_.Exception.Message }
    }
}

# Function to test Docker container
function Test-DockerContainer {
    param(
        [string]$ContainerName
    )
    
    try {
        Write-Host "Testing Docker container: $ContainerName..." -ForegroundColor Yellow
        $container = docker ps --filter "name=$ContainerName" --format "table {{.Names}}\t{{.Status}}" | Select-String $ContainerName
        
        if ($container) {
            Write-Host "✅ Container $ContainerName - Running" -ForegroundColor Green
            return @{ Name = "Container: $ContainerName"; Status = "PASS"; Details = "Running" }
        } else {
            Write-Host "❌ Container $ContainerName - Not running" -ForegroundColor Red
            return @{ Name = "Container: $ContainerName"; Status = "FAIL"; Details = "Not running" }
        }
    } catch {
        Write-Host "❌ Container $ContainerName - Error: $($_.Exception.Message)" -ForegroundColor Red
        return @{ Name = "Container: $ContainerName"; Status = "FAIL"; Details = $_.Exception.Message }
    }
}

Write-Host "`n📦 Testing Docker Containers" -ForegroundColor Cyan
Write-Host "=============================" -ForegroundColor Cyan

# Test Docker containers
$testResults += Test-DockerContainer "replantworld_postgres"
$testResults += Test-DockerContainer "replantworld_redis"
$testResults += Test-DockerContainer "replantworld_backend"
$testResults += Test-DockerContainer "replantworld_frontend"

Write-Host "`n🌐 Testing HTTP Endpoints" -ForegroundColor Cyan
Write-Host "=========================" -ForegroundColor Cyan

# Test HTTP endpoints
$testResults += Test-Endpoint "Backend Health Check" "http://localhost:8000/api/healthz/"
$testResults += Test-Endpoint "Frontend Application" "http://localhost:3000"

Write-Host "`n🔍 Testing Database Connectivity" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan

# Test database connectivity
try {
    Write-Host "Testing PostgreSQL connection..." -ForegroundColor Yellow
    $dbTest = docker exec replantworld_postgres pg_isready -U postgres
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ PostgreSQL - Connection OK" -ForegroundColor Green
        $testResults += @{ Name = "PostgreSQL Connection"; Status = "PASS"; Details = "Connection successful" }
    } else {
        Write-Host "❌ PostgreSQL - Connection failed" -ForegroundColor Red
        $testResults += @{ Name = "PostgreSQL Connection"; Status = "FAIL"; Details = "Connection failed" }
    }
} catch {
    Write-Host "❌ PostgreSQL - Error: $($_.Exception.Message)" -ForegroundColor Red
    $testResults += @{ Name = "PostgreSQL Connection"; Status = "FAIL"; Details = $_.Exception.Message }
}

# Test Redis connectivity
try {
    Write-Host "Testing Redis connection..." -ForegroundColor Yellow
    $redisTest = docker exec replantworld_redis redis-cli ping
    if ($redisTest -eq "PONG") {
        Write-Host "✅ Redis - Connection OK" -ForegroundColor Green
        $testResults += @{ Name = "Redis Connection"; Status = "PASS"; Details = "PONG received" }
    } else {
        Write-Host "❌ Redis - Connection failed" -ForegroundColor Red
        $testResults += @{ Name = "Redis Connection"; Status = "FAIL"; Details = "No PONG received" }
    }
} catch {
    Write-Host "❌ Redis - Error: $($_.Exception.Message)" -ForegroundColor Red
    $testResults += @{ Name = "Redis Connection"; Status = "FAIL"; Details = $_.Exception.Message }
}

Write-Host "`n📊 Test Results Summary" -ForegroundColor Cyan
Write-Host "=======================" -ForegroundColor Cyan

$passCount = ($testResults | Where-Object { $_.Status -eq "PASS" }).Count
$failCount = ($testResults | Where-Object { $_.Status -eq "FAIL" }).Count
$totalCount = $testResults.Count

Write-Host "`nTotal Tests: $totalCount" -ForegroundColor White
Write-Host "Passed: $passCount" -ForegroundColor Green
Write-Host "Failed: $failCount" -ForegroundColor Red

if ($failCount -eq 0) {
    Write-Host "`n🎉 All tests passed! Your development environment is ready." -ForegroundColor Green
} else {
    Write-Host "`n⚠️  Some tests failed. Please check the issues above." -ForegroundColor Yellow
}

Write-Host "`n📋 Detailed Results:" -ForegroundColor Cyan
foreach ($result in $testResults) {
    $statusColor = if ($result.Status -eq "PASS") { "Green" } else { "Red" }
    $statusIcon = if ($result.Status -eq "PASS") { "✅" } else { "❌" }
    Write-Host "$statusIcon $($result.Name): $($result.Status) - $($result.Details)" -ForegroundColor $statusColor
}

Write-Host "`n🔗 Quick Links:" -ForegroundColor Cyan
Write-Host "Frontend: http://localhost:3000" -ForegroundColor Blue
Write-Host "Backend API: http://localhost:8000" -ForegroundColor Blue
Write-Host "Health Check: http://localhost:8000/api/healthz/" -ForegroundColor Blue
Write-Host "Admin Panel: http://localhost:8000/admin/" -ForegroundColor Blue

Write-Host "`n📝 Next Steps:" -ForegroundColor Cyan
Write-Host "1. Set up Solana CLI: .\setup-solana.ps1" -ForegroundColor White
Write-Host "2. Create Django superuser: docker-compose exec backend python manage.py createsuperuser" -ForegroundColor White
Write-Host "3. Start developing your carbon credit NFT features!" -ForegroundColor White
