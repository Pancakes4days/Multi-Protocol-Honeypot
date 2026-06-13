#!/bin/bash
# Quick setup script for Minecraft Honeypot on DigitalOcean VPS

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
    echo "   Did you use the Docker marketplace image?"
    echo "   Or install Docker manually: curl -fsSL https://get.docker.com | sh"
    exit 1
fi

echo " Docker is installed: $(docker --version)"
echo ""

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "   Installing docker-compose..."
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
fi

echo "   docker-compose is available: $(docker-compose --version)"
echo ""

# Create logs directory
echo "   Creating logs directory..."
mkdir -p logs
echo "   Logs directory created"
echo ""

# Build the honeypot
echo "   Building honeypot Docker image..."
docker-compose build
echo "   Image built successfully"
echo ""

# Start the honeypot
echo "   Starting honeypot..."
docker-compose up -d
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
echo "   docker-compose down"
echo ""
echo "   More info: See README.md"
echo ""
echo 
