#!/usr/bin/env bash

############################################
# Pyronear Pi Zero Watchdog Setup Script
#
# This script will:
# 1. Update the Raspberry Pi system
# 2. Install required packages
# 3. Clone the pyro-engine repository
# 4. Make the watchdog script executable
# 5. Create the log file
# 6. Install a cron job that runs every 10 minutes
############################################

set -e

############################################
# Variables
############################################
USER_HOME="/home/pi"
REPO_URL="https://github.com/pyronear/pyro-engine.git"
REPO_DIR="$USER_HOME/pyro-engine"
WATCHDOG_SCRIPT="$REPO_DIR/watchdog/pi_zero/watchdog.py"
LOG_FILE="$USER_HOME/watchdog.log"

############################################
# Update system
############################################
echo "Updating system packages..."
sudo apt update
sudo apt upgrade -y

############################################
# Install required packages
############################################
echo "Installing required packages..."
sudo apt install -y \
    git \
    python3 \
    python3-pip \
    python3-venv \
    cron

############################################
# Clone repo if missing, otherwise update it
############################################
if [ ! -d "$REPO_DIR" ]; then
    echo "Cloning pyro-engine repository..."
    cd "$USER_HOME"
    git clone --single-branch --branch watchdog "$REPO_URL" "$REPO_DIR"
else
    echo "Repository already exists, updating it..."
    cd "$REPO_DIR"
    git fetch origin
    git checkout watchdog
    git pull origin watchdog
fi

############################################
# Make watchdog executable
############################################
echo "Making watchdog script executable..."
chmod +x "$WATCHDOG_SCRIPT"

############################################
# Create log file
############################################
echo "Creating log file..."
touch "$LOG_FILE"

############################################
# Ensure cron service is enabled and running
############################################
echo "Ensuring cron service is running..."
sudo systemctl enable cron
sudo systemctl start cron

############################################
# Add cron job safely
# This works even if no crontab exists yet
############################################
CRON_JOB="*/10 * * * * /usr/bin/python3 $WATCHDOG_SCRIPT >> $LOG_FILE 2>&1"

echo "Setting up cron job..."

CURRENT_CRONTAB="$(crontab -l 2>/dev/null || true)"

if echo "$CURRENT_CRONTAB" | grep -Fq "$WATCHDOG_SCRIPT"; then
    echo "Cron job already exists. Skipping."
else
    {
        echo "$CURRENT_CRONTAB"
        echo "$CRON_JOB"
    } | crontab -
    echo "Cron job added."
fi

############################################
# Final status
############################################
echo ""
echo "======================================"
echo "Setup complete"
echo "Watchdog will run every 10 minutes"
echo ""
echo "Watchdog script:"
echo "$WATCHDOG_SCRIPT"
echo ""
echo "Log file:"
echo "$LOG_FILE"
echo ""
echo "Current crontab:"
crontab -l || true
echo "======================================"
echo ""
echo "To monitor logs:"
echo "tail -f $LOG_FILE"
