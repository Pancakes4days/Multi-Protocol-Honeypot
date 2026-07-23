#!/bin/bash
# Quick setup script for Minecraft Honeypot on a Hetzner Cloud VPS

set -e  # Exit on any error

echo "=================================="
echo " MINECRAFT HONEYPOT SETUP"
echo "=================================="
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
    echo "   Don't run as root! Run as your honeypot user."
    echo "   Example: ssh honeypot@YOUR_VPS_IP"
    exit 1
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "   Docker is not installed!"
    echo "   Did you create the server from Hetzner's 'Docker CE' app image?"
    echo "   Or install Docker manually: curl -fsSL https://get.docker.com | sh"
    exit 1
fi

echo " Docker is installed: $(docker --version)"
echo ""

# Check that the Docker Compose v2 plugin is available (`docker compose`, with a
# space). The old standalone `docker-compose` binary is deprecated and isn't in
# Ubuntu's default repos; modern Docker ships Compose as a plugin. The Hetzner
# "Docker CE" app image already includes it.
if ! docker compose version &> /dev/null; then
    echo "   Docker Compose plugin not found!"
    echo "   Install it with: sudo apt update && sudo apt install -y docker-compose-plugin"
    exit 1
fi

echo "   Docker Compose is available: $(docker compose version)"
echo ""

# Create logs directory
echo "   Creating logs directory..."
mkdir -p logs
echo "   Logs directory created"
echo ""

# Record this user's UID/GID so the container runs as you and can write to
# ./logs. Written to .env, which docker compose reads automatically for every
# subsequent command (up, restart, etc.).
echo "   Configuring container user..."
printf 'HONEYPOT_UID=%s\nHONEYPOT_GID=%s\n' "$(id -u)" "$(id -g)" > .env
echo "   Container will run as UID:GID $(id -u):$(id -g)"
echo ""

# Build the honeypot
echo "   Building honeypot Docker image..."
docker compose build
echo "   Image built successfully"
echo ""

# Start the honeypot
echo "   Starting honeypot..."
docker compose up -d
echo "   Honeypot started!"
echo ""

# Wait a moment
sleep 2

# Check if it's running
if docker ps | grep -q minecraft-honeypot; then
    echo "   Honeypot is running!"
    echo ""
    docker ps --filter name=minecraft-honeypot
    echo ""
else
    echo "   Honeypot failed to start!"
    echo "   Check logs: docker logs minecraft-honeypot"
    exit 1
fi

# Get server IP
SERVER_IP=$(curl -s ifconfig.me || echo "YOUR_VPS_IP")

echo "=================================="
echo " SETUP COMPLETE"
echo "=================================="
echo ""
echo "  Your honeypot is now running and listening for attacks!"
echo ""
echo "   Server IP: $SERVER_IP"
echo "   Port: 25565"
echo ""
echo "   View live logs:"
echo "   docker logs -f minecraft-honeypot"
echo ""
echo "   Analyze attacks:"
echo "   python3 analyze_logs.py"
echo ""
echo "   Test from your computer:"
echo "   python3 attack_simulator.py $SERVER_IP"
echo ""
echo "   Stop the honeypot:"
echo "   docker compose down"
echo ""
echo "   More info: See README.md"
echo ""
echo 
