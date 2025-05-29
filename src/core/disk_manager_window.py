import subprocess
import psutil
import os
import platform
import ctypes
import re
from ctypes import windll, wintypes
from .safety import SafetyManager

# For Windows WMI queries
try:
    import wmi # type: ignore
    import win32com.client # type: ignore
    import pythoncom # type: ignore
except ImportError:
    pass

class DiskManager:
    def __init__(self):
        self.safety = SafetyManager()
        # Initialize WMI for Windows only to avoid errors on other platforms
        if platform.system() == "Windows":
            try:
                pythoncom.CoInitialize()  # Initialize COM for the current thread
                self.wmi_conn = wmi.WMI()
            except:
                self.wmi_conn = None
    
    def list_physical_disks(self):
        """List all physical disk devices (not partitions) on Windows"""
        physical_disks = []
        
        try:
            # For Windows systems
            if platform.system() == "Windows" and self.wmi_conn:
                # Using WMI to get physical disks
                for disk in self.wmi_conn.Win32_DiskDrive():
                    # Get device path (\\.\PHYSICALDRIVEx format)
                    device_path = disk.DeviceID
                    
                    # Get size in a readable format
                    size = "Unknown"
                    if disk.Size:
                        size = self._format_size(int(disk.Size))
                    
                    # Get model information
                    model = disk.Model.strip() if disk.Model else "Unknown"
                    
                    # Determine if the disk is removable
                    is_removable = disk.MediaType and ("removable" in disk.MediaType.lower() or 
                                                        "external" in disk.MediaType.lower())
                    
                    physical_disks.append({
                        'device': device_path,
                        'size': size,
                        'model': model,
                        'removable': is_removable
                    })
            
            return physical_disks
        except Exception as e:
            print(f"Error listing physical disks: {str(e)}")
            return []
    
    def list_partitions(self):
        """List all partitions on the system"""
        partitions = []
        
        try:
            # For Windows systems
            if platform.system() == "Windows" and self.wmi_conn:
                # Method 1: Use WMI to get logical disks and their associated partitions
                
                # First get all logical disks (drives with letters)
                logical_disks = {}
                for logical_disk in self.wmi_conn.Win32_LogicalDisk():
                    drive_letter = logical_disk.DeviceID
                    logical_disks[logical_disk.DeviceID] = {
                        'size': logical_disk.Size and int(logical_disk.Size),
                        'free': logical_disk.FreeSpace and int(logical_disk.FreeSpace)
                    }
                
                # Then get partition information and match with logical disks
                for partition in self.wmi_conn.Win32_DiskPartition():
                    # Find the associated logical disk for this partition
                    associated_disks = self.wmi_conn.Win32_LogicalDiskToPartition(Dependent=partition.DeviceID)
                    
                    for assoc in associated_disks:
                        # The Antecedent contains the logical disk reference
                        match = re.search(r'Win32_LogicalDisk.DeviceID="([^"]+)"', assoc.Antecedent)
                        drive_letter = match.group(1) if match else None
                        
                        logical_disk_info = logical_disks.get(drive_letter, {})
                        size = logical_disk_info.get('size', 0)
                        free = logical_disk_info.get('free', 0)
                        
                        # Calculate used space and percentage
                        used = size - free if size and free else None
                        percent_used = (used / size) * 100 if used and size else None
                        
                        # Format size for display
                        size_str = self._format_size(size) if size else "Unknown"
                        
                        partitions.append({
                            'device': partition.DeviceID,
                            'size': size_str,
                            'type': partition.Type,
                            'mountpoint': drive_letter,
                            'used': used,
                            'free': free,
                            'percent_used': percent_used
                        })
                
                # Method 2: Use psutil as a fallback or complement
                for part in psutil.disk_partitions(all=True):
                    # Skip if we've already added this partition
                    if any(p.get('mountpoint') == part.device for p in partitions):
                        continue
                    
                    # Skip certain drive types (CD-ROMs, network drives)
                    if part.opts and ('cdrom' in part.opts or 'remote' in part.opts):
                        continue
                    
                    usage = None
                    used = free = percent = None
                    try:
                        if part.mountpoint:
                            usage = psutil.disk_usage(part.mountpoint)
                            used = usage.used
                            free = usage.free
                            percent = usage.percent
                    except:
                        pass
                    
                    partitions.append({
                        'device': part.device,
                        'size': "Unknown",
                        'type': part.fstype,
                        'mountpoint': part.mountpoint,
                        'used': used,
                        'free': free,
                        'percent_used': percent
                    })
            
            return partitions
        except Exception as e:
            print(f"Error listing partitions: {str(e)}")
            return []
    
    def _is_removable(self, device_path):
        """Check if a device is removable on Windows"""
        try:
            if self.wmi_conn:
                # Extract disk number from device path (\\.\PHYSICALDRIVEx)
                disk_num = device_path.split('PHYSICALDRIVE')[-1]
                
                # Query the specific disk
                for disk in self.wmi_conn.Win32_DiskDrive(Index=disk_num):
                    # Check if it's removable based on MediaType
                    return disk.MediaType and ("removable" in disk.MediaType.lower() or 
                                              "external" in disk.MediaType.lower())
            return False
        except:
            return False
    
    def _format_size(self, size_bytes):
        """Convert bytes to human-readable size format"""
        if not size_bytes:
            return "Unknown"
            
        size_bytes = float(size_bytes)
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f}{unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f}PB"
    
    def format_device(self, device_path, filesystem='ntfs'):
        """Format a device with specified filesystem"""
        if not self.safety.is_safe_device(device_path):
            raise ValueError(f"Cannot format system device: {device_path}")
        
        if not self.safety.get_confirmation(device_path, "format"):
            return False
        
        # Format based on filesystem using Windows format command
        try:
            # Need to convert device path to drive letter
            # This is a simplified approach - in practice you need to map from 
            # physical device to volume/drive letter
            
            # For this example, we assume device_path is already a drive letter (e.g., "D:")
            if filesystem == 'ntfs':
                format_cmd = ["format", device_path, "/fs:ntfs", "/q", "/y"]
            elif filesystem == 'fat32':
                format_cmd = ["format", device_path, "/fs:fat32", "/q", "/y"]
            elif filesystem == 'exfat':
                format_cmd = ["format", device_path, "/fs:exfat", "/q", "/y"]
            else:
                raise ValueError(f"Unsupported filesystem: {filesystem}")
            
            result = subprocess.run(
                format_cmd,
                capture_output=True,
                text=True,
                check=True
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"Format failed: {e.stderr}")
            return False
    
    def _unmount_device(self, device_path):
        """Safely unmount/eject a device on Windows"""
        try:
            # For Windows, this would typically involve sending a "removal request"
            # to the operating system. For a drive letter (e.g. "D:"):
            
            # This is a placeholder - in a real implementation you would use 
            # the Windows API via ctypes to safely eject/unmount
            pass
        except:
            pass
    
    def mount_device(self, device_path, mount_point=None):
        """Mount a device to a specified drive letter in Windows
        Note: Windows typically auto-mounts devices with drive letters,
        this would be used for special cases like mounting VHDs or
        assigning a specific drive letter"""
        try:
            # This is a simplified approach
            # In practice, you would use Windows API calls via ctypes or win32api
            # to mount devices that aren't automatically mounted
            
            # For VHD mounting example:
            if device_path.lower().endswith('.vhd') or device_path.lower().endswith('.vhdx'):
                if os.path.exists(device_path):
                    result = subprocess.run(
                        ["powershell", "-Command", f"Mount-VHD -Path '{device_path}' -PassThru"],
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    return True
            
            # For assigning drive letters, you'd use DiskPart or mountvol commands
            return False  # Not implemented for general case
        except Exception as e:
            print(f"Mount failed: {str(e)}")
            return False
    
    def __del__(self):
        """Clean up WMI connection when object is destroyed"""
        if platform.system() == "Windows":
            try:
                pythoncom.CoUninitialize()  # Clean up COM for the current thread
            except:
                pass