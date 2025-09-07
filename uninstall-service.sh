#!/bin/bash
# MeshCore Bot Service Uninstallation Script
# This script removes the MeshCore Bot systemd service

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

echo -e "${BLUE}MeshCore Bot Service Uninstaller${NC}"
echo "===================================="

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}This script must be run as root (use sudo)${NC}"
   exit 1
fi

echo -e "${YELLOW}Step 1: Stopping and disabling service${NC}"
# Stop service if running
if systemctl is-active --quiet "$SERVICE_NAME"; then
    systemctl stop "$SERVICE_NAME"
    echo -e "${GREEN}Stopped $SERVICE_NAME service${NC}"
else
    echo -e "${YELLOW}Service $SERVICE_NAME is not running${NC}"
fi

# Disable service
if systemctl is-enabled --quiet "$SERVICE_NAME"; then
    systemctl disable "$SERVICE_NAME"
    echo -e "${GREEN}Disabled $SERVICE_NAME service${NC}"
else
    echo -e "${YELLOW}Service $SERVICE_NAME is not enabled${NC}"
fi

echo -e "${YELLOW}Step 2: Removing systemd service file${NC}"
# Remove service file
if [ -f "/etc/systemd/system/$SERVICE_NAME.service" ]; then
    rm "/etc/systemd/system/$SERVICE_NAME.service"
    echo -e "${GREEN}Removed service file${NC}"
else
    echo -e "${YELLOW}Service file not found${NC}"
fi

# Reload systemd
systemctl daemon-reload
echo -e "${GREEN}Reloaded systemd configuration${NC}"

echo -e "${YELLOW}Step 3: Removing installation directory${NC}"
# Remove installation directory
if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
    echo -e "${GREEN}Removed installation directory: $INSTALL_DIR${NC}"
else
    echo -e "${YELLOW}Installation directory not found${NC}"
fi

echo -e "${YELLOW}Step 4: Removing log directory${NC}"
# Remove log directory
if [ -d "$LOG_DIR" ]; then
    rm -rf "$LOG_DIR"
    echo -e "${GREEN}Removed log directory: $LOG_DIR${NC}"
else
    echo -e "${YELLOW}Log directory not found${NC}"
fi

echo -e "${YELLOW}Step 5: Removing service user${NC}"
# Remove service user
if id "$SERVICE_USER" &>/dev/null; then
    userdel "$SERVICE_USER"
    echo -e "${GREEN}Removed user: $SERVICE_USER${NC}"
else
    echo -e "${YELLOW}User $SERVICE_USER not found${NC}"
fi

echo ""
echo -e "${GREEN}Uninstallation completed successfully!${NC}"
echo ""
echo -e "${BLUE}What was removed:${NC}"
echo "  - Systemd service file"
echo "  - Installation directory: $INSTALL_DIR"
echo "  - Log directory: $LOG_DIR"
echo "  - Service user: $SERVICE_USER"
echo ""
echo -e "${YELLOW}Note: Python packages installed via pip are not removed${NC}"
echo -e "${YELLOW}If you want to remove them, run: pip3 uninstall -r requirements.txt${NC}"
