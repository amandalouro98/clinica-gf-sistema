#!/bin/bash

# Script de setup inicial do VPS Locaweb
# Executar como root na primeira vez

set -e

echo "========================================="
echo "  Setup VPS - Gabriela Franco Sistema"
echo "========================================="

# Atualizar sistema
echo "[1/7] Atualizando sistema..."
apt update && apt upgrade -y

# Instalar dependências
echo "[2/7] Instalando dependências..."
apt install -y curl wget git nano ufw fail2ban

# Instalar Docker
echo "[3/7] Instalando Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
    usermod -aG docker root
    systemctl enable docker
    systemctl start docker
    echo "Docker instalado com sucesso!"
else
    echo "Docker já instalado."
fi

# Instalar Docker Compose
echo "[4/7] Instalando Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    curl -L "https://github.com/docker/compose/releases/download/v2.23.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    echo "Docker Compose instalado!"
else
    echo "Docker Compose já instalado."
fi

# Configurar firewall
echo "[5/7] Configurando firewall..."
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
echo "Firewall configurado!"

# Criar estrutura de diretórios
echo "[6/7] Criando estrutura de diretórios..."
mkdir -p /opt/clinica-gf
mkdir -p /opt/clinica-gf/backups
mkdir -p /opt/clinica-gf/certbot/conf
mkdir -p /opt/clinica-gf/certbot/www
echo "Diretórios criados!"

# Configurar fail2ban (proteção contra ataques)
echo "[7/7] Configurando fail2ban..."
systemctl enable fail2ban
systemctl start fail2ban

echo ""
echo "========================================="
echo "  Setup concluído com sucesso!"
echo "========================================="
echo ""
echo "Próximos passos:"
echo "1. Copie os arquivos do sistema para /opt/clinica-gf/"
echo "2. Execute: cd /opt/clinica-gf && docker-compose up -d"
echo "3. Configure o certificado SSL com certbot"
echo ""
echo "IP do servidor: $(hostname -I | awk '{print $1}')"
