#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Instala o Ubuntu no WSL2 e configura o Docker Engine sem Docker Desktop.

.DESCRIPTION
    1. Habilita WSL2 e Virtual Machine Platform
    2. Instala Ubuntu 24.04 via WSL
    3. Executa scripts/setup_wsl_docker.sh dentro do Ubuntu para instalar Docker Engine
    4. Configura o contexto Docker no Windows para apontar para o WSL2

.USAGE
    # Abra o PowerShell como Administrador e execute:
    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
    .\scripts\setup_wsl_ubuntu.ps1
#>

$ErrorActionPreference = "Stop"

function Write-Step { param($msg) Write-Host "`n==> $msg" -ForegroundColor Cyan }

# ── 1. Habilitar recursos do Windows ─────────────────────────────────────────
Write-Step "Habilitando WSL e Virtual Machine Platform..."
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart

# ── 2. Definir WSL2 como padrão ───────────────────────────────────────────────
Write-Step "Definindo WSL2 como versão padrão..."
wsl --set-default-version 2

# ── 3. Instalar Ubuntu 24.04 ──────────────────────────────────────────────────
$distros = wsl -l -v 2>&1
if ($distros -match "Ubuntu") {
    Write-Host "Ubuntu já instalado, pulando." -ForegroundColor Yellow
} else {
    Write-Step "Instalando Ubuntu 24.04 no WSL2..."
    wsl --install -d Ubuntu-24.04
    Write-Host "AGUARDE: o Ubuntu está sendo instalado. Pode ser solicitado criar usuário/senha." -ForegroundColor Yellow
    Write-Host "Após criar o usuário, feche a janela do Ubuntu e execute este script novamente para continuar." -ForegroundColor Yellow
    exit 0
}

# ── 4. Copiar e executar o script de instalação do Docker ────────────────────
Write-Step "Instalando Docker Engine no Ubuntu WSL2..."
$scriptPath = (Resolve-Path ".\scripts\setup_wsl_docker.sh").Path
# Converter para caminho WSL
$wslPath = $scriptPath -replace "\\", "/" -replace "^([A-Z]):", { "/mnt/" + $_.Groups[1].Value.ToLower() }

wsl -d Ubuntu-24.04 -- bash -c "sed 's/\r$//' '$wslPath' | sudo bash"

# ── 5. Configurar contexto Docker no Windows ─────────────────────────────────
Write-Step "Configurando contexto Docker 'wsl2' no Windows..."
try {
    docker context create wsl2 --docker "host=unix:///var/run/docker.sock" 2>$null
} catch {}
docker context use wsl2

Write-Step "Verificando instalação..."
docker version
docker compose version

Write-Host @"

✅ Docker Engine no WSL2 configurado com sucesso!

Para usar Docker a partir do PowerShell:
  docker ps
  docker compose up -d

Para acessar o Ubuntu diretamente:
  wsl -d Ubuntu-24.04

Para iniciar o Docker Engine se parar:
  wsl -d Ubuntu-24.04 -- sudo service docker start
"@ -ForegroundColor Green
