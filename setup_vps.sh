#!/usr/bin/env bash
# =============================================================================
# Script de instalacion y arranque 24/7 para Servidores Linux / VPS / Raspberry Pi
# =============================================================================

set -e

echo "============================================================"
echo "    INSTALADOR 24/7 - PULL&BEAR RESTOCK BOT (LINUX / VPS)"
echo "============================================================"
echo ""

# Verificar si Docker esta instalado
if ! command -v docker &> /dev/null; then
    echo "Instalando Docker y Docker Compose..."
    sudo apt-get update
    sudo apt-get install -y ca-certificates curl gnupg
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg

    echo \
      "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
      sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi

echo "Asegurando que config.json este en modo headless para servidor..."
python3 -c "import json; c=json.load(open('config.json')); c['headless']=True; json.dump(c, open('config.json', 'w'), indent=2)" 2>/dev/null || true

echo "Construyendo y arrancando contenedor en segundo plano (24/7)..."
sudo docker compose up -d --build

echo ""
echo "============================================================"
echo "✅ ¡El bot esta corriendo 24/7 en segundo plano!"
echo "Para ver los logs en tiempo real, ejecuta:"
echo "   sudo docker logs -f pullandbear_restock_bot"
echo "============================================================"
