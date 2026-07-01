param()

$ErrorActionPreference = 'Stop'

$RootDir = Split-Path -Path $MyInvocation.MyCommand.Path -Parent
Set-Location $RootDir

Write-Host '[deploy] Building Docker image using existing cache...' -ForegroundColor Cyan
docker compose build

Write-Host '[deploy] Starting containers...' -ForegroundColor Cyan
docker compose up -d

Write-Host '[deploy] Current containers:' -ForegroundColor Cyan
docker compose ps

Write-Host '[deploy] Recent logs:' -ForegroundColor Cyan
docker compose logs --no-color --tail 30

Write-Host '[deploy] Deployment completed.' -ForegroundColor Green
