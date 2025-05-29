# DiskForge 🔧

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS%20%7C%20Windows-lightgrey.svg)](https://github.com/yourusername/diskforge)

**DiskForge** is a powerful, cross-platform disk management tool designed for formatting drives and creating bootable Linux USB drives. It provides both a modern graphical interface and a comprehensive command-line interface, working seamlessly across Linux, macOS, and Windows.

## ✨ Features

### 🖥️ Cross-Platform Support
- **Linux**: Full native support with udev integration
- **macOS**: Native disk utilities integration
- **Windows**: WMI-based disk management

### 🛡️ Safety First
- Automatic system drive detection and protection
- Multi-level confirmation for destructive operations
- Real-time removable device detection
- Comprehensive safety warnings based on risk assessment

### 💾 Disk Operations
- **Format drives** with multiple filesystem support:
  - ext4, fat32, ntfs, exfat
- **Create bootable USB drives** from ISO files:
  - Multiple creation methods (dd, ISO9660, hybrid, Windows)
  - Auto-detection of ISO types
  - Real-time progress tracking with cancellation support
- **List and monitor** physical disks and partitions
- **Real-time disk information** with automatic refresh

### 🎨 Dual Interface
- **GUI Mode**: Modern PyQt6-based interface with:
  - Tabbed interface for different operations
  - Real-time progress bars
  - Drag-and-drop ISO selection
  - Automatic device detection and refresh
- **CLI Mode**: Comprehensive command-line interface with:
  - Colored output for better readability
  - Interactive confirmations
  - Progress tracking
  - Scriptable operations

## 🚀 Quick Start

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/diskforge.git
   cd diskforge
   ```

2. **Run the installation script:**
   ```bash
   ./install.sh
   ```

3. **Or install manually:**
   ```bash
   pip install -r requirements.txt
   pip install -e .
   ```

### Usage

#### GUI Mode (Default)
```bash
diskforge
# or
diskforge-gui
```

#### CLI Mode
```bash
# Interactive CLI
diskforge --cli

# Direct commands
diskforge --cli list disks
diskforge --cli list partitions
diskforge --cli format /dev/sdb1 --filesystem fat32
diskforge --cli create-usb ubuntu.iso /dev/sdb --method auto
diskforge --cli info
```

## 📋 Requirements

### System Requirements
- **Python**: 3.8 or newer
- **Operating System**: Linux, macOS, or Windows
- **Privileges**: Root/Administrator access for disk operations

### Python Dependencies
- `psutil` - Cross-platform system information
- `click` - Command-line interface framework
- `colorama` - Colored terminal output
- `PyQt6` - GUI framework (optional, for GUI mode)

### Platform-Specific Dependencies
- **Linux**: `pyudev` - Device monitoring
- **macOS**: `pyobjc` - macOS system integration
- **Windows**: `pywin32`, `wmi` - Windows system APIs

## 🖼️ Screenshots

### GUI Interface
The GUI provides an intuitive tabbed interface:

- **Disk Information Tab**: Real-time view of physical disks and partitions
- **Format Tab**: Safe disk formatting with confirmation dialogs
- **USB Creator Tab**: Bootable USB creation with progress tracking
- **System Info Tab**: Comprehensive system information display

### CLI Interface
The CLI offers powerful command-line operations:

```bash
$ diskforge --cli list disks

Physical Disks:
Device          Size       Removable  Model
/dev/sda        1TB        No         Samsung SSD 970
/dev/sdb        32GB       Yes        SanDisk Ultra USB
```

## ⚠️ Safety Features

DiskForge implements multiple layers of safety to prevent accidental data loss:

### 🛡️ System Protection
- **System Drive Detection**: Automatically identifies and protects boot/system drives
- **Mount Point Analysis**: Checks for critical mount points (/, /boot, /efi, etc.)
- **Risk Assessment**: Three-tier warning system (low, high, critical)

### 🔒 User Confirmation
- **Multi-step Confirmation**: Different confirmation levels based on risk
- **Device Verification**: Users must type exact device names for high-risk operations
- **Visual Warnings**: Clear color-coded warnings and progress indicators

### 📱 Real-time Monitoring
- **Live Device Detection**: Automatic detection of plugged/unplugged devices
- **Progress Tracking**: Real-time progress with cancellation support
- **Status Updates**: Detailed status messages throughout operations

## 🏗️ Architecture

DiskForge is built with a modular architecture:

```
src/
├── core/                 # Core functionality
│   ├── disk_manager.py   # Platform abstraction layer
│   ├── disk_manager_linux.py
│   ├── disk_manager_mac.py
│   ├── disk_manager_windows.py
│   ├── usb_creator.py    # Bootable USB creation
│   └── safety.py         # Safety management
├── cli/                  # Command-line interface
│   └── commands.py       # CLI commands and parsing
├── gui/                  # Graphical interface
│   └── main_window.py    # PyQt6 main window
└── main.py              # Application entry point
```

## 🤝 Contributing

We welcome contributions! Please see our contributing guidelines:

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Submit a pull request

### Development Setup
```bash
git clone https://github.com/yourusername/diskforge.git
cd diskforge
pip install -e ".[dev]"  # Install with development dependencies
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

**IMPORTANT**: DiskForge is a powerful tool that can permanently delete data. Always:
- Backup important data before using disk operations
- Double-check device selections before confirming operations
- Test on non-critical systems first
- Understand that the developers are not responsible for data loss

## 🐛 Bug Reports & Feature Requests

Please use GitHub Issues to report bugs or request features:
- [Bug Report](https://github.com/yourusername/diskforge/issues/new?template=bug_report.md)
- [Feature Request](https://github.com/yourusername/diskforge/issues/new?template=feature_request.md)

## 📞 Support

- **Documentation**: [Wiki](https://github.com/yourusername/diskforge/wiki)
- **Community**: [Discussions](https://github.com/yourusername/diskforge/discussions)
- **Issues**: [GitHub Issues](https://github.com/yourusername/diskforge/issues)

---

**Made with ❤️ by the DiskForge team**
