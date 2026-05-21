#!/usr/bin/env bash
# =============================================================================
# setup_wsl_docker.sh
# Instala o Docker Engine no Ubuntu (WSL2) sem Docker Desktop.
# Compatível com Ubuntu 22.04 / 24.04.
#
# Uso (dentro do WSL2 Ubuntu):
#   bash -c "sed 's/\r$//' setup_wsl_docker.sh | sudo bash"
# =============================================================================

# Reexecutar sem CRLF se necessário (proteção contra Windows line endings)
if file "$0" 2>/dev/null | grep -q CRLF; then
    tmp=$(mktemp)
    sed 's/\r$//' "$0" > "$tmp"
    exec bash "$tmp" "$@"
fi

set -euo pipefail

GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'
step() { echo -e "\n${CYAN}==> $1${NC}"; }
ok()   { echo -e "${GREEN}✔  $1${NC}"; }

# Verificar se está rodando como root
if [[ $EUID -ne 0 ]]; then
    echo "Re-executando com sudo..."
    exec sudo bash "$0" "$@"
fi

# ── 1. Dependências ───────────────────────────────────────────────────────────
step "Atualizando pacotes e instalando dependências..."
apt-get update -qq
apt-get install -y --no-install-recommends \
    ca-certificates curl gnupg lsb-release iptables

# ── 2. Repositório oficial Docker ─────────────────────────────────────────────
step "Adicionando repositório Docker..."
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" \
  > /etc/apt/sources.list.d/docker.list

# ── 3. Instalar Docker Engine ──────────────────────────────────────────────────
step "Instalando Docker Engine + Compose plugin..."
apt-get update -qq
apt-get install -y docker-ce docker-ce-cli containerd.io \
    docker-buildx-plugin docker-compose-plugin

# ── 4. Adicionar usuário atual ao grupo docker ────────────────────────────────
REAL_USER="${SUDO_USER:-$(logname 2>/dev/null || echo '')}"
if [[ -n "$REAL_USER" && "$REAL_USER" != "root" ]]; then
    step "Adicionando '$REAL_USER' ao grupo docker..."
    usermod -aG docker "$REAL_USER"
    ok "Usuário '$REAL_USER' adicionado. Reabra o terminal para ter efeito."
fi

# ── 5. Configurar Docker para iniciar com WSL2 ────────────────────────────────
# No WSL2, systemd pode não estar disponível em versões antigas.
# Usamos /etc/wsl.conf para habilitar systemd (Ubuntu 22.04+ suporta)
step "Configurando WSL2 para iniciar o Docker automaticamente..."

WSL_CONF="/etc/wsl.conf"
if ! grep -q "\[boot\]" "$WSL_CONF" 2>/dev/null; then
    cat >> "$WSL_CONF" <<'EOF'

[boot]
systemd=true
EOF
    ok "systemd habilitado no WSL2 (/etc/wsl.conf)."
fi

# Habilitar e iniciar o serviço Docker
if systemctl is-active --quiet docker 2>/dev/null; then
    ok "Docker já está rodando."
else
    systemctl enable docker 2>/dev/null || true
    service docker start 2>/dev/null || true
fi

# ── 6. Verificar ──────────────────────────────────────────────────────────────
step "Verificando instalação..."
docker --version
docker compose version

echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN} Docker Engine instalado com sucesso no WSL2!               ${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""
echo "PRÓXIMOS PASSOS:"
echo "  1. Feche esta janela e execute no PowerShell:"
echo "       wsl --shutdown"
echo "       wsl -d Ubuntu-24.04"
echo "  2. Dentro do Ubuntu, verifique: docker ps"
echo "  3. Do PowerShell configure o contexto:"
echo "       docker context create wsl2 --docker 'host=unix:///var/run/docker.sock'"
echo "       docker context use wsl2"
echo "  4. Suba os serviços do projeto:"
echo "       docker compose up -d"
