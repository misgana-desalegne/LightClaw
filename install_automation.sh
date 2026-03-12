#!/bin/bash
# Install LightClaw Automation Service
# This script sets up the automation as a systemd service

set -e

echo "================================================"
echo "LightClaw Automation Service Installer"
echo "================================================"
echo

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Please run as root or with sudo"
    exit 1
fi

# Get the actual user (not root)
ACTUAL_USER="${SUDO_USER:-$USER}"
LIGHTCLAW_DIR="/home/$ACTUAL_USER/LightClaw"

echo "📋 Configuration:"
echo "   User: $ACTUAL_USER"
echo "   Directory: $LIGHTCLAW_DIR"
echo

# Check if directory exists
if [ ! -d "$LIGHTCLAW_DIR" ]; then
    echo "❌ LightClaw directory not found: $LIGHTCLAW_DIR"
    exit 1
fi

# Check if automation script exists
if [ ! -f "$LIGHTCLAW_DIR/automation_pipeline.py" ]; then
    echo "❌ automation_pipeline.py not found"
    exit 1
fi

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip3 install schedule || {
    echo "❌ Failed to install schedule package"
    exit 1
}

# Create logs directory
echo "📁 Creating logs directory..."
mkdir -p "$LIGHTCLAW_DIR/logs"
chown $ACTUAL_USER:$ACTUAL_USER "$LIGHTCLAW_DIR/logs"

# Update service file with correct user and paths
echo "⚙️  Configuring service file..."
SERVICE_FILE="$LIGHTCLAW_DIR/lightclaw-automation.service"

# Replace placeholders in service file
sed -i "s|User=misgun|User=$ACTUAL_USER|g" "$SERVICE_FILE"
sed -i "s|WorkingDirectory=/home/misgun/LightClaw|WorkingDirectory=$LIGHTCLAW_DIR|g" "$SERVICE_FILE"
sed -i "s|ExecStart=/usr/bin/python3 /home/misgun/LightClaw/automation_pipeline.py|ExecStart=/usr/bin/python3 $LIGHTCLAW_DIR/automation_pipeline.py|g" "$SERVICE_FILE"
sed -i "s|StandardOutput=append:/home/misgun/LightClaw/logs/|StandardOutput=append:$LIGHTCLAW_DIR/logs/|g" "$SERVICE_FILE"
sed -i "s|StandardError=append:/home/misgun/LightClaw/logs/|StandardError=append:$LIGHTCLAW_DIR/logs/|g" "$SERVICE_FILE"

# Check for environment variables
echo
echo "🔐 Checking OAuth credentials..."
if [ -z "$GOOGLE_OAUTH_CLIENT_ID" ] || [ -z "$GOOGLE_OAUTH_CLIENT_SECRET" ]; then
    echo "⚠️  OAuth credentials not set in environment"
    echo
    echo "Please set these in /etc/environment or the service file:"
    echo "   GOOGLE_OAUTH_CLIENT_ID=your-client-id"
    echo "   GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret"
    echo
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Copy service file to systemd
echo "📋 Installing systemd service..."
cp "$SERVICE_FILE" /etc/systemd/system/lightclaw-automation.service
chmod 644 /etc/systemd/system/lightclaw-automation.service

# Reload systemd
echo "🔄 Reloading systemd..."
systemctl daemon-reload

# Enable service
echo "✅ Enabling service..."
systemctl enable lightclaw-automation.service

echo
echo "================================================"
echo "✅ Installation complete!"
echo "================================================"
echo
echo "📋 Service commands:"
echo "   Start:   sudo systemctl start lightclaw-automation"
echo "   Stop:    sudo systemctl stop lightclaw-automation"
echo "   Status:  sudo systemctl status lightclaw-automation"
echo "   Logs:    sudo journalctl -u lightclaw-automation -f"
echo "   Restart: sudo systemctl restart lightclaw-automation"
echo
echo "📂 Log files:"
echo "   Main:   $LIGHTCLAW_DIR/logs/automation.log"
echo "   Stdout: $LIGHTCLAW_DIR/logs/automation_stdout.log"
echo "   Stderr: $LIGHTCLAW_DIR/logs/automation_stderr.log"
echo
echo "⚠️  Important: Authenticate with YouTube before starting:"
echo "   1. Start your LightClaw agent"
echo "   2. Navigate to /admin"
echo "   3. Connect Google Account"
echo "   4. Grant YouTube permissions"
echo
echo "🚀 To start now: sudo systemctl start lightclaw-automation"
echo
