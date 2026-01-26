#!/bin/bash
# Quick installation script for Personal Voice Assistant

echo "======================================"
echo "Personal Voice Assistant - Setup"
echo "======================================"
echo ""

# Check Python version
echo "✓ Checking Python..."
python3 --version || { echo "✗ Python 3 not found"; exit 1; }

# Navigate to directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"
echo "✓ Working directory: $SCRIPT_DIR"

# Create virtual environment (optional)
read -p "Create virtual environment? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    echo "✓ Virtual environment activated"
fi

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "======================================"
echo "✓ Setup complete!"
echo "======================================"
echo ""
echo "To start the Voice Assistant, run:"
echo "  python main.py"
echo ""
echo "For advanced version with more features:"
echo "  python advanced.py"
echo ""
echo "To run tests and diagnostics:"
echo "  python setup.py"
echo ""
