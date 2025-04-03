#!/bin/bash

# Script to install SMS Gateway as a systemd service on Debian with venv

# Variables
SERVICE_NAME="sms-gateway"
INSTALL_DIR="/opt/sms-gateway"
USER="freebsd"  # Change to desired user or leave as root
VENV_DIR="$INSTALL_DIR/venv"
PYTHON_BIN="/usr/bin/python3"  # System Python to create venv
VENV_PYTHON="$VENV_DIR/bin/python3"  # Python in venv for service
LOG_DIR="/var/log/sms-gateway"
CONFIG_FILE="$INSTALL_DIR/config.json"
REQUIREMENTS_FILE="$INSTALL_DIR/requirements.txt"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "This script must be run as root. Use sudo."
    exit 1
fi

# Check if requirements.txt exists
if [ ! -f "requirements.txt" ]; then
    echo "Error: requirements.txt not found in current directory."
    echo "Please create it with dependencies (e.g., gsmmodem, requests) and rerun."
    exit 1
fi

# Create user if it doesn't exist
if ! id "$USER" >/dev/null 2>&1; then
    useradd -m -s /bin/bash "$USER"
    echo "Created user $USER"#!/bin/bash

# Script to install SMS Gateway as a systemd service on Debian with venv

# Variables
SERVICE_NAME="sms-gateway"
INSTALL_DIR="/opt/sms-gateway"
USER="smsuser"  # Change to desired user or leave as root
VENV_DIR="$INSTALL_DIR/venv"
PYTHON_BIN="/usr/bin/python3"  # System Python to create venv
VENV_PYTHON="$VENV_DIR/bin/python3"  # Python in venv for service
LOG_DIR="/var/log/sms-gateway"
CONFIG_FILE="$INSTALL_DIR/config.json"
REQUIREMENTS_FILE="$INSTALL_DIR/requirements.txt"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "This script must be run as root. Use sudo."
    exit 1
fi

# Check if requirements.txt exists
if [ ! -f "requirements.txt" ]; then
    echo "Error: requirements.txt not found in current directory."
    echo "Please create it with dependencies (e.g., gsmmodem, requests) and rerun."
    exit 1
fi

# Create user if it doesn't exist
if ! id "$USER" >/dev/null 2>&1; then
    useradd -m -s /bin/bash "$USER"
    echo "Created user $USER"
fi

# Add user to dialout group for modem access
usermod -aG dialout "$USER"
echo "Added $USER to dialout group for modem access"

# Create install directory
mkdir -p "$INSTALL_DIR"
chown "$USER:$USER" "$INSTALL_DIR"

# Copy files to install directory
echo "Copying SMS Gateway files to $INSTALL_DIR..."
cp -r ./* "$INSTALL_DIR/"
chown -R "$USER:$USER" "$INSTALL_DIR"

# Create log directory
mkdir -p "$LOG_DIR"
chown "$USER:$USER" "$LOG_DIR"

# Install Python3 and venv if not already installed
echo "Installing Python3 and venv..."
apt update
apt install -y python3 python3-venv

# Create and activate virtual environment
echo "Creating virtual environment in $VENV_DIR..."
"$PYTHON_BIN" -m venv "$VENV_DIR"
chown -R "$USER:$USER" "$VENV_DIR"

# Install dependencies from requirements.txt
echo "Installing dependencies from $REQUIREMENTS_FILE..."
"$VENV_PYTHON" -m pip install --upgrade pip
"$VENV_PYTHON" -m pip install -r "$REQUIREMENTS_FILE"

# Create systemd service file
echo "Creating systemd service file..."
cat > /etc/systemd/system/$SERVICE_NAME.service <<EOF
[Unit]
Description=SMS Gateway Service
After=network.target

[Service]
ExecStart=$VENV_PYTHON $INSTALL_DIR/main.py
WorkingDirectory=$INSTALL_DIR
User=$USER
Group=$USER
Restart=always
StandardOutput=append:$LOG_DIR/sms-gateway.log
StandardError=append:$LOG_DIR/sms-gateway.log

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd, enable and start service
systemctl daemon-reload
systemctl enable $SERVICE_NAME
systemctl start $SERVICE_NAME

# Check status
echo "Checking service status..."
systemctl status $SERVICE_NAME

echo "SMS Gateway installed and started as a service."
echo "Logs are in $LOG_DIR/sms-gateway.log"
echo "To stop: systemctl stop $SERVICE_NAME"
echo "To restart: systemctl restart $SERVICE_NAME"
echo "To uninstall: systemctl stop $SERVICE_NAME && systemctl disable $SERVICE_NAME && rm -rf $INSTALL_DIR /etc/systemd/system/$SERVICE_NAME.service"
fi

# Add user to dialout group for modem access
usermod -aG dialout "$USER"
echo "Added $USER to dialout group for modem access"

# Create install directory
mkdir -p "$INSTALL_DIR"
chown "$USER:$USER" "$INSTALL_DIR"

# Copy files to install directory
echo "Copying SMS Gateway files to $INSTALL_DIR..."
cp -r ./* "$INSTALL_DIR/"
chown -R "$USER:$USER" "$INSTALL_DIR"

# Create log directory
mkdir -p "$LOG_DIR"
chown "$USER:$USER" "$LOG_DIR"

# Install Python3 and venv if not already installed
echo "Installing Python3 and venv..."
apt update
apt install -y python3 python3-venv

# Create and activate virtual environment
echo "Creating virtual environment in $VENV_DIR..."
"$PYTHON_BIN" -m venv "$VENV_DIR"
chown -R "$USER:$USER" "$VENV_DIR"

# Install dependencies from requirements.txt
echo "Installing dependencies from $REQUIREMENTS_FILE..."
"$VENV_PYTHON" -m pip install --upgrade pip
"$VENV_PYTHON" -m pip install -r "$REQUIREMENTS_FILE"

# Create systemd service file
echo "Creating systemd service file..."
cat > /etc/systemd/system/$SERVICE_NAME.service <<EOF
[Unit]
Description=SMS Gateway Service
After=network.target

[Service]
ExecStart=$VENV_PYTHON $INSTALL_DIR/main.py
WorkingDirectory=$INSTALL_DIR
User=$USER
Group=$USER
Restart=always
StandardOutput=append:$LOG_DIR/sms-gateway.log
StandardError=append:$LOG_DIR/sms-gateway.log

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd, enable and start service
systemctl daemon-reload
systemctl enable $SERVICE_NAME
systemctl start $SERVICE_NAME

# Check status
echo "Checking service status..."
systemctl status $SERVICE_NAME

echo "SMS Gateway installed and started as a service."
echo "Logs are in $LOG_DIR/sms-gateway.log"
echo "To stop: systemctl stop $SERVICE_NAME"
echo "To restart: systemctl restart $SERVICE_NAME"
echo "To uninstall: systemctl stop $SERVICE_NAME && systemctl disable $SERVICE_NAME && rm -rf $INSTALL_DIR /etc/systemd/system/$SERVICE_NAME.service"