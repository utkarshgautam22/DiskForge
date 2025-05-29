#!/bin/bash
# DiskForge Installation Script

set -e

echo "🔧 DiskForge Installation Script"
echo "================================"
echo

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8 or newer."
    exit 1
fi

# Check Python version
python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "🐍 Python version: $python_version"

if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)"; then
    echo "❌ Python 3.8 or newer is required."
    exit 1
fi

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 is not installed. Please install pip."
    exit 1
fi

echo "✅ Python and pip are available"
echo

# Detect platform
platform=$(uname -s)
echo "🖥️  Platform: $platform"

# Install system dependencies based on platform
case $platform in
    "Linux")
        echo "Installing Linux dependencies..."
        if command -v apt-get &> /dev/null; then
            sudo apt-get update
            sudo apt-get install -y python3-dev libudev-dev
        elif command -v yum &> /dev/null; then
            sudo yum install -y python3-devel libudev-devel
        elif command -v pacman &> /dev/null; then
            sudo pacman -S python python-pip udev
        else
            echo "⚠️  Could not detect package manager. You may need to install development packages manually."
        fi
        ;;
    "Darwin")
        echo "Installing macOS dependencies..."
        if command -v brew &> /dev/null; then
            brew install python3
        else
            echo "⚠️  Homebrew not found. Please install it from https://brew.sh/"
        fi
        ;;
    *)
        echo "⚠️  Platform not fully supported. Continuing with Python packages only..."
        ;;
esac

echo
echo "📦 Installing Python dependencies..."

# Create virtual environment (optional but recommended)
read -p "🤔 Create a virtual environment? [Y/n]: " create_venv
case $create_venv in
    [Nn]* )
        echo "Installing globally..."
        ;;
    * )
        echo "Creating virtual environment..."
        python3 -m venv venv
        source venv/bin/activate
        echo "✅ Virtual environment activated"
        ;;
esac

# Install base requirements
echo "Installing base requirements..."
pip3 install -r requirements.txt

# Ask about GUI support
read -p "🖼️  Install GUI support (PyQt6)? [Y/n]: " install_gui
case $install_gui in
    [Nn]* )
        echo "Skipping GUI installation. CLI only."
        ;;
    * )
        echo "Installing GUI dependencies..."
        pip3 install PyQt6
        ;;
esac

# Install the package
echo
echo "🔧 Installing DiskForge..."
pip3 install -e .

echo
echo "✅ Installation complete!"
echo
echo "Usage:"
echo "  diskforge              # Launch GUI (if installed)"
echo "  diskforge --cli         # Launch CLI"
echo "  diskforge-cli           # Direct CLI access"
echo "  diskforge-gui           # Direct GUI access (if installed)"
echo
echo "⚠️  Note: DiskForge requires root/administrator privileges for disk operations."
echo "   Linux/macOS: sudo diskforge"
echo "   Windows: Run as Administrator"
echo
echo "📚 For more information, see the documentation."
