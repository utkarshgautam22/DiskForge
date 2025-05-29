import subprocess
import psutil
import os
from .safety import SafetyManager
import platform

class DiskManager:
    def __init__(self):
        self.safety = SafetyManager()
    
    def list_physical_disks(self):
        """List all physical disk devices (not partitions)"""
        physical_disks = []
        
        try:
            # For Linux systems
            if platform.system() == "Linux":
                # Using lsblk to get only physical disks (excluding partitions)
                result = subprocess.run(
                    ["lsblk", "-d", "-n", "-o", "NAME,SIZE,MODEL,VENDOR,TRAN,TYPE"],
                    capture_output=True,
                    text=True,
                    check=True
                )
                
                for line in result.stdout.strip().split('\n'):
                    if line:
                        parts = line.split()
                        if len(parts) >= 2 and parts[0].strip():
                            device_name = parts[0].strip()
                            device_path = f"/dev/{device_name}"
                            size = parts[1].strip() if len(parts) > 1 else "Unknown"
                            model = ' '.join(parts[2:-2]) if len(parts) > 4 else "Unknown"
                            
                            # Skip loop devices and CD-ROMs
                            if device_name.startswith('loop') or device_name.startswith('sr'):
                                continue
                            
                            # Get additional details
                            is_removable = self._is_removable(device_path)
                            
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
            # For Linux systems
            if platform.system() == "Linux":
                # Method 1: Use lsblk to get partitions
                result = subprocess.run(
                    ["lsblk", "-n", "-o", "NAME,SIZE,TYPE,MOUNTPOINT,FSTYPE"],
                    capture_output=True,
                    text=True,
                    check=True
                )
                
                for line in result.stdout.strip().split('\n'):
                    if line:
                        parts = line.split()
                        if len(parts) >= 3 and parts[2].strip() == "part":
                            # Extract device name, removing any tree characters
                            device_name = parts[0].strip()
                            if device_name.startswith('├─') or device_name.startswith('└─'):
                                device_name = device_name[2:]  # Remove tree characters
                            
                            device_path = f"/dev/{device_name}"
                            size = parts[1].strip() if len(parts) > 1 else "Unknown"
                            
                            # Skip pseudo partitions like device-mapper and loop devices
                            if (device_name.startswith('loop') or 
                                device_name.startswith('dm-') or 
                                'mapper' in device_name or
                                device_name.startswith('ram')):
                                continue
                                
                            # Get mountpoint and filesystem type if available
                            mountpoint = parts[3].strip() if len(parts) > 3 and parts[3].strip() != "" else None
                            fstype = parts[4].strip() if len(parts) > 4 else None
                            
                            # Fix the mountpoint field - sometimes lsblk shows the filesystem type in the mountpoint column
                            if mountpoint in ["ntfs", "vfat", "ext4", "ext3", "exfat", "btrfs", "xfs"] and not fstype:
                                fstype = mountpoint
                                mountpoint = None
                                
                            # Try to get disk usage info if mounted
                            used = free = percent = None
                            if mountpoint and mountpoint not in ["", "/", "/boot", "/boot/efi"] and os.path.ismount(mountpoint):
                                try:
                                    usage = psutil.disk_usage(mountpoint)
                                    used = usage.used
                                    free = usage.free
                                    percent = usage.percent
                                except Exception as e:
                                    print(f"Error getting disk usage for {mountpoint}: {str(e)}")
                                    pass
                                    
                            partitions.append({
                                'device': device_path,
                                'size': size,
                                'type': fstype,
                                'mountpoint': mountpoint,
                                'used': used,
                                'free': free,
                                'percent_used': percent
                            })
                            
            # Method 2: Use psutil as a fallback or complement
            for part in psutil.disk_partitions(all=True):
                # Skip if we've already added this partition from lsblk
                # Also handle variations with and without tree characters
                clean_device = part.device
                if any(p['device'] == clean_device for p in partitions):
                    continue
                    
                # Skip pseudo devices
                device_name = part.device.split('/')[-1]
                if (device_name.startswith('loop') or 
                    device_name.startswith('dm-') or 
                    device_name.startswith('ram') or 
                    'mapper' in device_name or
                    '/dev/zram' in part.device):
                    continue
                    
                # Skip pseudo filesystems
                if part.fstype in ('tmpfs', 'devtmpfs', 'devfs', 'overlay', 'squashfs',
                                  'proc', 'sysfs', 'cgroup', 'cgroup2', 'debugfs', 
                                  'pstore', 'bpf', 'tracefs', 'securityfs', 'ramfs',
                                  'devpts', 'efivarfs', 'autofs', 'hugetlbfs', 'mqueue',
                                  'fusectl', 'configfs', 'binfmt_misc', 'nsfs', 'fuse.portal',
                                  'fuse.gvfsd-fuse'):
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
                    'size': "Unknown",  # psutil doesn't provide size directly
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
        """Check if a device is removable"""
        try:
            # Extract device name from path (e.g., /dev/sda -> sda)
            device_name = device_path.split('/')[-1]
            # Check removable status from sysfs
            with open(f"/sys/block/{device_name}/removable", 'r') as f:
                return f.read().strip() == "1"
        except:
            return False
    
    def format_device(self, device_path, filesystem='ext4'):
        """Format a device with specified filesystem"""
        if not self.safety.is_safe_device(device_path):
            raise ValueError(f"Cannot format system device: {device_path}")
        
        if not self.safety.get_confirmation(device_path, "format"):
            return False
        
        # Unmount device first
        self._unmount_device(device_path)
        
        # Format command based on filesystem
        format_commands = {
            'ext4': ['mkfs.ext4', '-F', device_path],
            'fat32': ['mkfs.vfat', '-F', '32', device_path],
            'ntfs': ['mkfs.ntfs', '-f', device_path]
        }
        
        if filesystem not in format_commands:
            raise ValueError(f"Unsupported filesystem: {filesystem}")
        
        try:
            result = subprocess.run(
                format_commands[filesystem],
                capture_output=True,
                text=True,
                check=True
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"Format failed: {e.stderr}")
            return False
    
    def _unmount_device(self, device_path):
        """Safely unmount a device"""
        try:
            subprocess.run(['umount', device_path], check=False)
        except:
            pass

    def mount_device(self, device_path, mount_point):
        """Mount a device to a specified mount point"""
        if not os.path.exists(mount_point):
            os.makedirs(mount_point)
        
        try:
            subprocess.run(['mount', device_path, mount_point], check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Mount failed: {e.stderr}")
            return False
        
    
