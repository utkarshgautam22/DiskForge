import platform
import sys

# Import appropriate platform-specific module
system = platform.system()
if system == "Linux":
    from .disk_manager_linux import DiskManager
elif system == "Darwin":  # macOS
    from .disk_manager_mac import DiskManager
elif system == "Windows":
    from .disk_manager_window import DiskManager
else:
    raise ImportError(f"Unsupported operating system: {system}")

# The DiskManager class is now automatically imported from the platform-specific module
