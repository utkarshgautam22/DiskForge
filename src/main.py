#!/usr/bin/env python3
# filepath: /home/utkarsh/Desktop/DiskForge/src/main.py

"""
DiskForge - Cross-platform disk management tool
Supports both command-line and graphical user interfaces
"""

import sys
import os
import argparse
import platform
from pathlib import Path

# Add the src directory to the Python path
src_dir = Path(__file__).parent
sys.path.insert(0, str(src_dir))

def check_dependencies():
    """Check if required dependencies are available"""
    missing_deps = []
    
    try:
        import psutil
    except ImportError:
        missing_deps.append("psutil")
    
    try:
        import click
    except ImportError:
        missing_deps.append("click")
    
    try:
        import colorama
    except ImportError:
        missing_deps.append("colorama")
    
    # Platform-specific dependencies
    if platform.system() == "Linux":
        try:
            import pyudev
        except ImportError:
            missing_deps.append("pyudev (Linux)")
    
    elif platform.system() == "Darwin":
        try:
            import objc
        except ImportError:
            missing_deps.append("pyobjc (macOS)")
    
    elif platform.system() == "Windows":
        try:
            import win32api
            import wmi
        except ImportError:
            missing_deps.append("pywin32 and wmi (Windows)")
    
    if missing_deps:
        print("❌ Missing required dependencies:")
        for dep in missing_deps:
            print(f"   - {dep}")
        print("\nPlease install them using:")
        print("   pip install -r requirements.txt")
        return False
    
    return True

def check_permissions():
    """Check if the application has the necessary permissions"""
    if platform.system() in ["Linux", "Darwin"]:
        if os.geteuid() != 0:
            print("⚠️  Warning: DiskForge requires root privileges for disk operations.")
            print("   Some features may not work without sudo.")
            print("   Run with: sudo python -m src.main")
            return False
    
    elif platform.system() == "Windows":
        try:
            import ctypes
            if not ctypes.windll.shell32.IsUserAnAdmin():
                print("⚠️  Warning: DiskForge requires administrator privileges for disk operations.")
                print("   Some features may not work without running as administrator.")
                return False
        except:
            pass
    
    return True

def run_cli():
    """Run the command-line interface"""
    try:
        from src.cli.commands import cli
        cli()
    except ImportError as e:
        print(f"❌ Error importing CLI module: {e}")
        print("Make sure all dependencies are installed.")
        sys.exit(1)

def run_gui():
    """Run the graphical user interface"""
    try:
        # Check if PyQt6 is available
        try:
            from PyQt6.QtWidgets import QApplication
        except ImportError:
            print("❌ PyQt6 is required for GUI mode.")
            print("Install it using: pip install PyQt6")
            sys.exit(1)
        
        from src.gui.main_window import run_gui
        return run_gui()
    except ImportError as e:
        print(f"❌ Error importing GUI module: {e}")
        print("Make sure PyQt6 is installed.")
        sys.exit(1)

def main():
    """Main entry point for DiskForge"""
    parser = argparse.ArgumentParser(
        description="DiskForge - Cross-platform disk management tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Launch GUI (default)
  %(prog)s --cli                    # Launch CLI mode
  %(prog)s --cli list disks         # List physical disks
  %(prog)s --cli list partitions    # List partitions
  %(prog)s --cli format /dev/sdb1 --filesystem fat32  # Format device
  %(prog)s --cli create-usb ubuntu.iso /dev/sdb       # Create bootable USB
  %(prog)s --cli info               # Show system information

Safety Features:
  - Automatic detection of system/boot devices
  - Confirmation prompts for destructive operations
  - Removable device preference for USB creation
  - Real-time progress tracking with cancellation support
        """
    )
    
    parser.add_argument(
        "--cli", 
        action="store_true", 
        help="Run in command-line interface mode"
    )
    
    parser.add_argument(
        "--no-permission-check",
        action="store_true",
        help="Skip permission checks (not recommended)"
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version="DiskForge 0.1.0"
    )
    
    # Parse known args to handle CLI passthrough
    args, remaining = parser.parse_known_args()
    
    # Print banner
    print("🔧 DiskForge v0.1.0 - Cross-platform Disk Management Tool")
    print(f"   Running on {platform.system()} {platform.release()}")
    print()
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Check permissions unless explicitly skipped
    if not args.no_permission_check:
        check_permissions()
    
    # Determine interface mode
    # if args.cli or len(remaining) > 0:
    print("🖥️  Starting CLI mode...")
    print()
    
    # If there are remaining arguments, pass them to CLI
    if remaining:
        sys.argv = [sys.argv[0]] + remaining
    else:
        # Interactive CLI mode
        sys.argv = [sys.argv[0]]
    
    run_cli()
    # else:
    #     print("🖼️  Starting GUI mode...")
    #     print("   Use --cli flag for command-line interface")
    #     print()
        
    #     try:
    #         exit_code = run_gui()
    #         sys.exit(exit_code)
    #     except KeyboardInterrupt:
    #         print("\n👋 Goodbye!")
    #         sys.exit(0)
    #     except Exception as e:
    #         print(f"❌ GUI Error: {e}")
    #         print("\nTry CLI mode with: python -m src.main --cli")
    #         sys.exit(1)

if __name__ == "__main__":
    main()