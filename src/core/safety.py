import os
import psutil
import platform

class SafetyManager:
    def __init__(self):
        self.system_drives = self._get_system_drives()
        self.protected_mountpoints = self._get_protected_mountpoints()
    
    def _get_system_drives(self):
        """Identify system/boot drives to protect"""
        system_drives = set()
        
        if platform.system() == "Linux":
            # Add root partition and boot partitions
            try:
                with open('/proc/mounts', 'r') as f:
                    for line in f:
                        if line.startswith('/dev/') and (' / ' in line or ' /boot' in line or ' /efi' in line):
                            device = line.split()[0]
                            # Get the base device (remove partition numbers)
                            base_device = device.rstrip('0123456789')
                            system_drives.add(base_device)
                            system_drives.add(device)  # Also add the partition itself
            except Exception:
                pass
                
            # Also check /proc/cmdline for root device
            try:
                with open('/proc/cmdline', 'r') as f:
                    cmdline = f.read()
                    if 'root=' in cmdline:
                        import re
                        root_match = re.search(r'root=(/dev/[^\s]+)', cmdline)
                        if root_match:
                            root_device = root_match.group(1)
                            base_device = root_device.rstrip('0123456789')
                            system_drives.add(base_device)
                            system_drives.add(root_device)
            except Exception:
                pass
        
        elif platform.system() == "Darwin":
            # On macOS, protect the boot disk
            try:
                import subprocess
                result = subprocess.run(['diskutil', 'info', '/'], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if 'Device Node:' in line:
                            device = line.split(':')[1].strip()
                            base_device = device.rstrip('0123456789s')
                            system_drives.add(base_device)
                            system_drives.add(device)
            except Exception:
                pass
        
        elif platform.system() == "Windows":
            # On Windows, protect C: drive and system partitions
            try:
                import string
                for drive in string.ascii_uppercase:
                    drive_path = f"{drive}:\\"
                    if os.path.exists(drive_path):
                        try:
                            # Check if it's a system drive
                            if drive == 'C' or os.path.exists(f"{drive_path}Windows"):
                                system_drives.add(f"{drive}:")
                        except Exception:
                            continue
            except Exception:
                pass
        
        return system_drives
    
    def _get_protected_mountpoints(self):
        """Get list of protected mountpoints"""
        protected = {'/boot', '/efi', '/', '/usr', '/var', '/etc', '/bin', '/sbin'}
        
        if platform.system() == "Windows":
            protected.update({'C:\\', 'C:\\Windows', 'C:\\Program Files'})
        
        return protected
    
    def is_safe_device(self, device_path):
        """Check if device is safe to format"""
        # Check if it's a system drive
        if device_path in self.system_drives:
            return False
        
        # Check if any partition on this device is mounted on protected mountpoints
        try:
            partitions = psutil.disk_partitions()
            for partition in partitions:
                if partition.device.startswith(device_path) or device_path.startswith(partition.device):
                    if partition.mountpoint in self.protected_mountpoints:
                        return False
        except Exception:
            pass
        
        return True
    
    def get_device_info(self, device_path):
        """Get detailed information about a device for safety assessment"""
        info = {
            'is_system_device': device_path in self.system_drives,
            'is_removable': False,
            'mounted_partitions': [],
            'warning_level': 'low'
        }
        
        try:
            # Check if device is removable
            partitions = psutil.disk_partitions()
            for partition in partitions:
                if partition.device.startswith(device_path) or device_path.startswith(partition.device):
                    info['mounted_partitions'].append({
                        'device': partition.device,
                        'mountpoint': partition.mountpoint,
                        'fstype': partition.fstype
                    })
                    
                    # Check if mountpoint is protected
                    if partition.mountpoint in self.protected_mountpoints:
                        info['warning_level'] = 'critical'
                    elif partition.mountpoint in ['/', '/home', '/var', '/usr']:
                        info['warning_level'] = 'high'
        except Exception:
            pass
        
        # Additional checks for removable media
        try:
            if platform.system() == "Linux":
                # Check if device is in /sys/block and if it's removable
                device_name = os.path.basename(device_path)
                removable_path = f"/sys/block/{device_name}/removable"
                if os.path.exists(removable_path):
                    with open(removable_path, 'r') as f:
                        info['is_removable'] = f.read().strip() == '1'
        except Exception:
            pass
        
        return info
    
    def get_confirmation_message(self, device_path, operation):
        """Generate appropriate confirmation message based on safety assessment"""
        info = self.get_device_info(device_path)
        
        if info['warning_level'] == 'critical':
            return (
                f"🚨 CRITICAL WARNING 🚨\n\n"
                f"You are about to {operation} {device_path}\n"
                f"This device contains SYSTEM PARTITIONS that are critical for your computer to function!\n\n"
                f"Mounted partitions:\n"
                + "\n".join([f"  - {p['device']} → {p['mountpoint']}" for p in info['mounted_partitions']])
                + f"\n\nProceeding will likely make your system UNBOOTABLE!\n"
                f"Type 'I UNDERSTAND THE RISK' to continue:"
            )
        elif info['warning_level'] == 'high':
            return (
                f"⚠️  HIGH RISK WARNING ⚠️\n\n"
                f"You are about to {operation} {device_path}\n"
                f"This device contains important system data!\n\n"
                f"Mounted partitions:\n"
                + "\n".join([f"  - {p['device']} → {p['mountpoint']}" for p in info['mounted_partitions']])
                + f"\n\nType '{device_path}' to confirm:"
            )
        else:
            return (
                f"⚠️  You are about to {operation} {device_path}\n"
                f"This will PERMANENTLY DELETE all data on this device!\n\n"
                f"Type '{device_path}' to confirm:"
            )
    
    def get_user_confirmation(self, device_path, operation):
        """Get user confirmation with appropriate safety level"""
        message = self.get_confirmation_message(device_path, operation)
        print(message)
        
        info = self.get_device_info(device_path)
        
        user_input = input().strip()
        
        if info['warning_level'] == 'critical':
            return user_input == 'I UNDERSTAND THE RISK'
        else:
            return user_input == device_path
    
    def validate_operation(self, device_path, operation):
        """Validate if an operation should be allowed"""
        info = self.get_device_info(device_path)
        
        # Always block operations on system devices unless explicitly confirmed
        if info['is_system_device'] and info['warning_level'] == 'critical':
            return False, "Operation blocked: Critical system device"
        
        # For removable devices, allow with standard confirmation
        if info['is_removable']:
            return True, "Safe removable device"
        
        # For non-removable, non-system devices, require confirmation
        return True, "Requires confirmation"
