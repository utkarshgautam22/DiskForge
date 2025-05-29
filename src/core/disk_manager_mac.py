#!/usr/bin/env python3
# filepath: /home/utkarsh/Desktop/DiskForge/src/core/disk_manager_mac.py
import subprocess
import psutil
import os
import platform
import plistlib
from .safety import SafetyManager

class DiskManager:
    def __init__(self):
        self.safety = SafetyManager()
    
    def list_physical_disks(self):
        """List all physical disk devices (not partitions)"""
        physical_disks = []
        
        try:
            # For macOS systems
            if platform.system() == "Darwin":
                # Using diskutil to get physical disks
                result = subprocess.run(
                    ["diskutil", "list", "-plist", "physical"],
                    capture_output=True,
                    check=True
                )
                
                # Parse the plist output
                disks_info = plistlib.loads(result.stdout)
                
                for disk in disks_info.get('AllDisksAndPartitions', []):
                    device_name = disk.get('DeviceIdentifier', '')
                    device_path = f"/dev/{device_name}"
                    
                    # Get disk size
                    size_str = "Unknown"
                    size_bytes = disk.get('Size', 0)
                    if size_bytes:
                        size_str = self._format_size(size_bytes)
                    
                    # Get model information
                    model = "Unknown"
                    try:
                        info_result = subprocess.run(
                            ["diskutil", "info", "-plist", device_name],
                            capture_output=True,
                            check=True
                        )
                        disk_info = plistlib.loads(info_result.stdout)
                        model = disk_info.get('DeviceModel', 'Unknown')
                    except:
                        pass
                    
                    # Check if removable
                    is_removable = self._is_removable(device_path)
                    
                    physical_disks.append({
                        'device': device_path,
                        'size': size_str,
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
            # For macOS systems
            if platform.system() == "Darwin":
                # Method 1: Use diskutil to get partitions
                result = subprocess.run(
                    ["diskutil", "list", "-plist"],
                    capture_output=True,
                    check=True
                )
                
                # Parse the plist output
                disks_info = plistlib.loads(result.stdout)
                
                # Process all disks and their partitions
                for disk in disks_info.get('AllDisksAndPartitions', []):
                    # Skip whole disk entries
                    if 'Partitions' not in disk:
                        continue
                        
                    for part in disk.get('Partitions', []):
                        device_name = part.get('DeviceIdentifier', '')
                        device_path = f"/dev/{device_name}"
                        
                        # Get partition size
                        size_str = "Unknown"
                        size_bytes = part.get('Size', 0)
                        if size_bytes:
                            size_str = self._format_size(size_bytes)
                        
                        # Get filesystem type and mountpoint
                        fstype = part.get('Content', '')
                        mountpoint = part.get('MountPoint', None)
                        
                        # Skip system partitions
                        if fstype in ['Apple_APFS_Recovery', 'EFI', 'Apple_Boot'] or not fstype:
                            continue
                        
                        # Get disk usage if mounted
                        used = free = percent = None
                        if mountpoint and os.path.ismount(mountpoint):
                            try:
                                usage = psutil.disk_usage(mountpoint)
                                used = usage.used
                                free = usage.free
                                percent = usage.percent
                            except Exception as e:
                                print(f"Error getting disk usage for {mountpoint}: {str(e)}")
                        
                        partitions.append({
                            'device': device_path,
                            'size': size_str,
                            'type': fstype,
                            'mountpoint': mountpoint,
                            'used': used,
                            'free': free,
                            'percent_used': percent
                        })
                
                # Method 2: Use psutil as a fallback or complement
                for part in psutil.disk_partitions(all=True):
                    # Skip if we've already added this partition
                    if any(p['device'] == part.device for p in partitions):
                        continue
                    
                    # Skip pseudo filesystems
                    if part.fstype in ('devfs', 'autofs', 'none'):
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
        """Check if a device is removable on macOS"""
        try:
            # Extract device name from path
            device_name = device_path.split('/')[-1]
            
            # Use diskutil to get device info
            result = subprocess.run(
                ["diskutil", "info", "-plist", device_name],
                capture_output=True,
                check=True
            )
            
            # Parse the plist output
            disk_info = plistlib.loads(result.stdout)
            
            # Look for removable media or external indicators
            is_ejectable = disk_info.get('Ejectable', False)
            is_removable = disk_info.get('RemovableMedia', False)
            is_external = disk_info.get('External', False)
            
            return is_ejectable or is_removable or is_external
        except:
            return False
    
    def _format_size(self, size_bytes):
        """Convert bytes to human-readable size format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f}{unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f}PB"
    
    def format_device(self, device_path, filesystem='apfs'):
        """Format a device with specified filesystem"""
        if not self.safety.is_safe_device(device_path):
            raise ValueError(f"Cannot format system device: {device_path}")
        
        if not self.safety.get_confirmation(device_path, "format"):
            return False
        
        # Unmount device first
        self._unmount_device(device_path)
        
        # Extract device name
        device_name = device_path.split('/')[-1]
        
        # Format based on filesystem
        try:
            if filesystem == 'apfs':
                result = subprocess.run(
                    ["diskutil", "apfs", "create", device_name, "Untitled"],
                    capture_output=True,
                    text=True,
                    check=True
                )
            elif filesystem == 'hfs+':
                result = subprocess.run(
                    ["diskutil", "eraseDisk", "HFS+", "Untitled", device_name],
                    capture_output=True,
                    text=True,
                    check=True
                )
            elif filesystem == 'fat32':
                result = subprocess.run(
                    ["diskutil", "eraseDisk", "FAT32", "Untitled", device_name],
                    capture_output=True,
                    text=True,
                    check=True
                )
            elif filesystem == 'exfat':
                result = subprocess.run(
                    ["diskutil", "eraseDisk", "ExFAT", "Untitled", device_name],
                    capture_output=True,
                    text=True,
                    check=True
                )
            else:
                raise ValueError(f"Unsupported filesystem: {filesystem}")
                
            return True
        except subprocess.CalledProcessError as e:
            print(f"Format failed: {e.stderr}")
            return False
    
    def _unmount_device(self, device_path):
        """Safely unmount a device on macOS"""
        try:
            device_name = device_path.split('/')[-1]
            subprocess.run(['diskutil', 'unmount', device_name], check=False)
        except:
            pass
    
    def mount_device(self, device_path, mount_point=None):
        """Mount a device to a specified mount point (or let macOS decide if None)"""
        try:
            device_name = device_path.split('/')[-1]
            
            if mount_point:
                if not os.path.exists(mount_point):
                    os.makedirs(mount_point)
                subprocess.run(['diskutil', 'mount', '-mountPoint', mount_point, device_name], check=True)
            else:
                subprocess.run(['diskutil', 'mount', device_name], check=True)
            
            return True
        except subprocess.CalledProcessError as e:
            print(f"Mount failed: {e.stderr}")
            return False
