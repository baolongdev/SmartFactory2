#!/bin/bash
# Quick Start Script for SMARTFACTORY (Raspberry Pi + Python 3.11)

echo "==========================================="
echo "   SMARTFACTORY - Python 3.11 Environment"
echo "==========================================="

# Check Python 3.11
if ! command -v python3.11 &> /dev/null; then
    echo "❌ Python 3.11 not found!"
    echo "➡ Please install Python 3.11 before running this script."
    exit 1
fi

echo "✓ Python 3.11 detected"

# Create venv if not exists
if [ ! -d "env" ]; then
    echo "Creating virtual environment (env)..."
    python3.11 -m venv env
else
    echo "✓ Virtual environment exists"
fi

# Activate venv
echo "Activating virtual environment..."
source env/bin/activate

# Upgrade pip
echo "Upgrading pip/setuptools/wheel..."
pip install --upgrade pip setuptools wheel || {
    echo "❌ Failed to upgrade pip"
    exit 1
}

# Install dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt || {
    echo "❌ Failed to install standard dependencies"
}

# Install OpenCV via piwheels (ARM build)
echo "Installing OpenCV (piwheels build)..."
pip install --extra-index-url https://www.piwheels.org/simple opencv-python-headless==4.8.1.78 || {
    echo "❌ Failed to install OpenCV!"
}

# Ensure python-dotenv
echo "Installing python-dotenv..."
pip install python-dotenv || {
    echo "❌ Failed to install python-dotenv!"
    exit 1
}

# Create .env if not exists
if [ ! -f ".env" ]; then
    echo "Creating .env file..."
    cp .env.example .env
    echo "⚠️  Please edit .env with your MQTT/WIFI configurations"
fi

# Create data directories
echo "Creating data directories..."
mkdir -p data/logs data/calibration data/captured_images

# Run server
echo ""
echo "==========================================="
echo "     Starting SMARTFACTORY Flask Server"
echo "==========================================="
python run.py
