#!/bin/bash
# MeshCore Bot Service Installation Script
# This script installs the MeshCore Bot as a systemd service

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SERVICE_NAME="meshcore-bot"
SERVICE_USER="meshcore"
SERVICE_GROUP="meshcore"
INSTALL_DIR="/opt/meshcore-bot"
LOG_DIR="/var/log/meshcore-bot"
SERVICE_FILE="meshcore-bot.service"

echo -e "${BLUE}MeshCore Bot Service Installer${NC}"
echo "=================================="

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}This script must be run as root (use sudo)${NC}"
   exit 1
fi

# Check if systemd is available
if ! command -v systemctl &> /dev/null; then
    echo -e "${RED}systemd is not available on this system${NC}"
    exit 1
fi

echo -e "${YELLOW}Step 1: Creating service user and group${NC}"
# Create service user and group
if ! id "$SERVICE_USER" &>/dev/null; then
    useradd --system --no-create-home --shell /bin/false "$SERVICE_USER"
    echo -e "${GREEN}Created user: $SERVICE_USER${NC}"
else
    echo -e "${YELLOW}User $SERVICE_USER already exists${NC}"
fi

echo -e "${YELLOW}Step 2: Creating directories${NC}"
# Create installation directory
mkdir -p "$INSTALL_DIR"
echo -e "${GREEN}Created directory: $INSTALL_DIR${NC}"

# Create log directory
mkdir -p "$LOG_DIR"
echo -e "${GREEN}Created directory: $LOG_DIR${NC}"

echo -e "${YELLOW}Step 3: Copying bot files${NC}"
# Copy bot files to installation directory
cp -r . "$INSTALL_DIR/"
echo -e "${GREEN}Copied bot files to $INSTALL_DIR${NC}"

echo -e "${YELLOW}Step 4: Setting permissions${NC}"
# Set ownership
chown -R "$SERVICE_USER:$SERVICE_GROUP" "$INSTALL_DIR"
chown -R "$SERVICE_USER:$SERVICE_GROUP" "$LOG_DIR"

# Set permissions
chmod 755 "$INSTALL_DIR"
chmod 644 "$INSTALL_DIR"/*.py
chmod 644 "$INSTALL_DIR"/*.ini
chmod 644 "$INSTALL_DIR"/*.txt
chmod 755 "$INSTALL_DIR"/modules
chmod 644 "$INSTALL_DIR"/modules/*.py
chmod 755 "$INSTALL_DIR"/modules/commands
chmod 644 "$INSTALL_DIR"/modules/commands/*.py

# Make main script executable
chmod 755 "$INSTALL_DIR/meshcore_bot.py"

echo -e "${GREEN}Set permissions for bot files${NC}"

echo -e "${YELLOW}Step 5: Installing systemd service${NC}"
# Copy service file to systemd directory
cp "$SERVICE_FILE" "/etc/systemd/system/"
echo -e "${GREEN}Copied service file to /etc/systemd/system/${NC}"

# Reload systemd
systemctl daemon-reload
echo -e "${GREEN}Reloaded systemd configuration${NC}"

echo -e "${YELLOW}Step 6: Enabling service${NC}"
# Enable service to start on boot
systemctl enable "$SERVICE_NAME"
echo -e "${GREEN}Enabled $SERVICE_NAME service${NC}"

echo -e "${YELLOW}Step 7: Installing Python dependencies${NC}"
# Install Python dependencies
if command -v pip3 &> /dev/null; then
    pip3 install -r "$INSTALL_DIR/requirements.txt"
    echo -e "${GREEN}Installed Python dependencies${NC}"
else
    echo -e "${YELLOW}pip3 not found, please install dependencies manually${NC}"
fi

echo ""
echo -e "${GREEN}Installation completed successfully!${NC}"
echo ""
echo -e "${BLUE}Service Management Commands:${NC}"
echo "  Start service:    sudo systemctl start $SERVICE_NAME"
echo "  Stop service:     sudo systemctl stop $SERVICE_NAME"
echo "  Restart service:  sudo systemctl restart $SERVICE_NAME"
echo "  Check status:     sudo systemctl status $SERVICE_NAME"
echo "  View logs:        sudo journalctl -u $SERVICE_NAME -f"
echo "  Disable service:  sudo systemctl disable $SERVICE_NAME"
echo ""
echo -e "${BLUE}Configuration:${NC}"
echo "  Config file:      $INSTALL_DIR/config.ini"
echo "  Log directory:    $LOG_DIR"
echo "  Working directory: $INSTALL_DIR"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Edit configuration: sudo nano $INSTALL_DIR/config.ini"
echo "2. Start the service: sudo systemctl start $SERVICE_NAME"
echo "3. Check status: sudo systemctl status $SERVICE_NAME"
echo ""
echo -e "${GREEN}The bot will now start automatically on system boot!${NC}"
