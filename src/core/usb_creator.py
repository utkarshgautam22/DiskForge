
import os
import time
import subprocess
import platform
import shutil
import threading
import psutil
from .safety import SafetyManager

class USBCreator:
    """
    A class for creating bootable USB drives from ISO files
    Supports Linux, macOS, and Windows
    """
    
    def __init__(self):
        self.safety = SafetyManager()
        self.system = platform.system()
        self._progress = 0
        self._status = "Idle"
        self._running = False
        self._thread = None
    
    @property
    def status(self):
        """Get the current status of the USB creation process"""
        return self._status
    
    @property
    def progress(self):
        """Get the current progress (0-100) of the USB creation process"""
        return self._progress
    
    @property
    def is_running(self):
        """Check if a USB creation process is currently running"""
        return self._running
    
    def create_bootable_usb(self, iso_path, target_device, method='dd', callback=None):
        """
        Create a bootable USB from an ISO file
        
        Args:
            iso_path (str): Path to the ISO file
            target_device (str): Path to the target device (e.g., /dev/sdb)
            method (str): Method to use for creating the bootable USB
                          'dd': Direct copy (works for most Linux ISOs)
                          'iso9660': For standard ISO9660 images
                          'hybrid': For hybrid ISOs (works with most modern Linux distros)
                          'windows': For Windows ISOs
                          'auto': Auto-detect the best method
            callback (function): Optional callback function for progress updates
                               Function signature: callback(progress_percent, status_message)
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not os.path.exists(iso_path):
            self._status = f"Error: ISO file not found: {iso_path}"
            return False
        
        # Check if it's safe to write to the target device
        if not self.safety.is_safe_device(target_device):
            self._status = f"Error: Cannot write to system device: {target_device}"
            return False
        
        # Get confirmation from the user via SafetyManager
        if not self.safety.get_confirmation(target_device, "create bootable USB"):
            self._status = "Operation cancelled by user"
            return False
        
        # Determine the best method if 'auto' is selected
        if method == 'auto':
            method = self._determine_best_method(iso_path)
        
        # Start the creation in a separate thread to not block the UI
        self._thread = threading.Thread(
            target=self._create_bootable_usb_thread,
            args=(iso_path, target_device, method, callback),
            daemon=True
        )
        self._running = True
        self._thread.start()
        return True
    
    def cancel(self):
        """Cancel an ongoing USB creation process"""
        self._running = False
        self._status = "Cancelled by user"
        # The thread will exit at the next check of self._running
        return True
    
    def _update_progress(self, progress, status, callback=None):
        """Update the progress and status, then call the callback if provided"""
        self._progress = progress
        self._status = status
        if callback:
            callback(progress, status)
    
    def _determine_best_method(self, iso_path):
        """Determine the best method for creating a bootable USB based on the ISO"""
        # Check if it's a Windows ISO
        if self._is_windows_iso(iso_path):
            return 'windows'
        
        # Check if it's a hybrid ISO
        if self._is_hybrid_iso(iso_path):
            return 'hybrid'
        
        # Default to dd method which works for most Linux distributions
        return 'dd'
    
    def _is_windows_iso(self, iso_path):
        """Check if the given ISO is a Windows installation media"""
        try:
            # Look for typical Windows files in the ISO
            if self.system == "Windows":
                check_cmd = ["powershell", "-Command", f"Get-ChildItem -Path $([System.IO.Path]::GetTempPath()) -Recurse -Filter 'sources' | Where-Object {{ $_.PSIsContainer }}"]
            else:
                check_cmd = ["isoinfo", "-J", "-i", iso_path, "-x", "/sources/install.wim"]
            
            result = subprocess.run(check_cmd, capture_output=True, text=True)
            return result.returncode == 0
        except:
            return False
    
    def _is_hybrid_iso(self, iso_path):
        """Check if the given ISO is a hybrid ISO (usable with dd)"""
        try:
            # Look for typical EFI boot markers
            if self.system != "Windows":
                check_cmd = ["isoinfo", "-J", "-i", iso_path, "-x", "/EFI/BOOT/"]
                result = subprocess.run(check_cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    return True
            
            # Check for isolinux
            if self.system != "Windows":
                check_cmd = ["isoinfo", "-J", "-i", iso_path, "-x", "/isolinux/"]
                result = subprocess.run(check_cmd, capture_output=True, text=True)
                return result.returncode == 0
            else:
                return True  # Assume hybrid on Windows for safety
        except:
            return True  # Assume hybrid for safety
    
    def _create_bootable_usb_thread(self, iso_path, target_device, method, callback):
        """Thread function to create a bootable USB"""
        try:
            self._update_progress(0, f"Starting USB creation with {method} method", callback)
            
            # Unmount target device first
            self._unmount_device(target_device)
            
            # Create bootable USB using the appropriate method
            if method == 'dd' or method == 'hybrid':
                success = self._dd_method(iso_path, target_device, callback)
            elif method == 'windows':
                success = self._windows_method(iso_path, target_device, callback)
            else:
                success = self._iso9660_method(iso_path, target_device, callback)
            
            if success and self._running:
                self._update_progress(100, "Bootable USB created successfully", callback)
                return True
            elif not self._running:
                self._update_progress(0, "Operation cancelled", callback)
                return False
            else:
                self._update_progress(0, "Failed to create bootable USB", callback)
                return False
                
        except Exception as e:
            self._update_progress(0, f"Error creating bootable USB: {str(e)}", callback)
            return False
        finally:
            self._running = False
    
    def _unmount_device(self, device_path):
        """Unmount all partitions of a device before writing to it"""
        if self.system == "Linux":
            try:
                # Find all mounted partitions from this device
                device_name = device_path.split('/')[-1]
                base_device = device_name.rstrip('0123456789')
                
                for part in psutil.disk_partitions():
                    if base_device in part.device:
                        subprocess.run(['umount', part.device], check=False)
            except:
                pass
        elif self.system == "Darwin":  # macOS
            try:
                device_name = device_path.split('/')[-1]
                subprocess.run(['diskutil', 'unmountDisk', device_name], check=False)
            except:
                pass
        elif self.system == "Windows":
            # Windows typically handles this automatically
            pass
    
    def _dd_method(self, iso_path, target_device, callback):
        """Create bootable USB using direct disk copy (dd)"""
        if self.system == "Windows":
            # On Windows, use a different approach since dd is not available
            return self._dd_windows_alternative(iso_path, target_device, callback)
            
        # Get ISO file size for progress calculation
        iso_size = os.path.getsize(iso_path)
        
        # Start dd process
        self._update_progress(2, "Starting direct disk write", callback)
        
        # Use different command based on OS
        if self.system == "Linux":
            cmd = ['sudo', 'dd', f'if={iso_path}', f'of={target_device}', 'bs=4M', 'status=progress']
        elif self.system == "Darwin":  # macOS
            cmd = ['dd', f'if={iso_path}', f'of={target_device}', 'bs=4m']
        else:
            self._update_progress(0, "Unsupported operating system for dd method", callback)
            return False
        
        # Execute command and monitor progress
        try:
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                universal_newlines=True
            )
            
            # Monitor progress
            last_progress = 0
            while process.poll() is None and self._running:
                # Check written bytes for progress updates
                if self.system == "Linux":
                    try:
                        # For Linux, check target device size change
                        written_bytes = os.path.getsize(target_device)
                        progress = min(int((written_bytes / iso_size) * 100), 99)
                        if progress > last_progress:
                            self._update_progress(progress, f"Writing ISO to device: {progress}%", callback)
                            last_progress = progress
                    except:
                        pass
                
                time.sleep(0.5)
                
            # Check if process completed successfully
            if not self._running:
                process.terminate()
                return False
                
            return_code = process.wait()
            
            self._update_progress(100, "Write completed, syncing disk cache...", callback)
            
            # Ensure data is written to disk
            if self.system == "Linux":
                subprocess.run(['sync'], check=False)
            
            return return_code == 0
            
        except Exception as e:
            self._update_progress(0, f"Error during DD process: {str(e)}", callback)
            return False
    
    def _dd_windows_alternative(self, iso_path, target_device, callback):
        """Alternative to dd for Windows systems using Win32 Disk Imager logic"""
        self._update_progress(5, "Starting USB creation on Windows", callback)
        
        try:
            # On Windows, we need to use PowerShell or third-party tools
            # For this example, we'll use PowerShell commands that mimic dd functionality
            
            # Convert device path to Windows format if needed
            # For example, convert /dev/sdb to \\.\PhysicalDrive1
            if target_device.startswith("/dev/"):
                disk_num = target_device.split("/dev/")[1]
                if disk_num.startswith("sd"):
                    disk_num = ord(disk_num[2]) - ord('a')  # Convert sda -> 0, sdb -> 1, etc.
                elif disk_num.isdigit():
                    disk_num = int(disk_num)
                else:
                    self._update_progress(0, f"Invalid device format for Windows: {target_device}", callback)
                    return False
                
                target_device = f"\\\\.\\PhysicalDrive{disk_num}"
            
            # PowerShell command to write the ISO to the USB drive
            ps_cmd = (
                f"$bytes = [System.IO.File]::ReadAllBytes('{iso_path}'); "
                f"$file = [System.IO.File]::OpenWrite('{target_device}'); "
                f"$file.Write($bytes, 0, $bytes.Length); "
                f"$file.Close();"
            )
            
            self._update_progress(10, "Writing ISO to device (this may take a while)", callback)
            
            # Run PowerShell command
            process = subprocess.Popen(
                ["powershell", "-Command", ps_cmd],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            # This is simplified - in a real implementation you would 
            # report progress as the file is written
            while process.poll() is None and self._running:
                time.sleep(1)
                
            if not self._running:
                process.terminate()
                return False
                
            return_code = process.wait()
            return return_code == 0
        
        except Exception as e:
            self._update_progress(0, f"Error during Windows ISO write: {str(e)}", callback)
            return False
    
    def _windows_method(self, iso_path, target_device, callback):
        """Create bootable USB specifically for Windows ISOs"""
        self._update_progress(10, "Starting Windows bootable USB creation", callback)
        
        # For Windows ISOs, we need to:
        # 1. Format the USB drive with FAT32 or NTFS
        # 2. Extract the ISO contents to the USB drive
        
        if self.system == "Windows":
            try:
                # Format the drive (assuming target_device is a drive letter like F:)
                drive_letter = target_device
                if not drive_letter.endswith(':'):
                    # Try to get the drive letter from the physical disk
                    self._update_progress(0, "Error: Need drive letter for Windows bootable USB", callback)
                    return False
                
                # Format with NTFS
                self._update_progress(30, "Formatting drive", callback)
                format_cmd = ["format", drive_letter, "/fs:NTFS", "/q", "/y"]
                subprocess.run(format_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                # Extract ISO contents
                self._update_progress(50, "Extracting ISO contents to USB", callback)
                extract_cmd = [
                    "powershell", 
                    "-Command", 
                    f"$mount = Mount-DiskImage -ImagePath '{iso_path}' -PassThru; "
                    f"$drive = ($mount | Get-Volume).DriveLetter; "
                    f"Copy-Item -Path $($drive + ':\\*') -Destination '{drive_letter}\\' -Recurse -Force; "
                    f"Dismount-DiskImage -ImagePath '{iso_path}';"
                ]
                subprocess.run(extract_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                self._update_progress(90, "Making USB bootable", callback)
                return True
                
            except Exception as e:
                self._update_progress(0, f"Error creating Windows bootable USB: {str(e)}", callback)
                return False
        else:
            # On Linux/macOS, we format and then extract the ISO
            try:
                # Format the drive
                self._update_progress(20, "Formatting drive", callback)
                if self.system == "Linux":
                    subprocess.run(['sudo', 'mkfs.ntfs', '-f', target_device], check=True)
                elif self.system == "Darwin":  # macOS
                    device_name = target_device.split('/')[-1]
                    subprocess.run(['diskutil', 'eraseDisk', 'MS-DOS', 'WINDOWS', 'MBR', device_name], check=True)
                
                # Mount the drive
                self._update_progress(40, "Mounting drive", callback)
                mount_point = "/tmp/usb_mount"
                if not os.path.exists(mount_point):
                    os.makedirs(mount_point)
                
                if self.system == "Linux":
                    subprocess.run(['sudo', 'mount', target_device, mount_point], check=True)
                elif self.system == "Darwin":
                    # macOS automatically mounts the drive - find the mount point
                    result = subprocess.run(
                        ['diskutil', 'info', target_device.split('/')[-1]], 
                        capture_output=True, 
                        text=True, 
                        check=True
                    )
                    for line in result.stdout.splitlines():
                        if "Mount Point:" in line:
                            mount_point = line.split(":", 1)[1].strip()
                            break
                
                # Mount the ISO
                self._update_progress(50, "Mounting ISO", callback)
                iso_mount = "/tmp/iso_mount"
                if not os.path.exists(iso_mount):
                    os.makedirs(iso_mount)
                
                if self.system == "Linux":
                    subprocess.run(['sudo', 'mount', '-o', 'loop', iso_path, iso_mount], check=True)
                elif self.system == "Darwin":
                    # On macOS, the ISO will automatically mount
                    result = subprocess.run(
                        ['hdiutil', 'attach', iso_path], 
                        capture_output=True, 
                        text=True, 
                        check=True
                    )
                    for line in result.stdout.splitlines():
                        if "/Volumes/" in line:
                            iso_mount = line.split(None, 2)[2].strip()
                            break
                
                # Copy ISO contents
                self._update_progress(60, "Copying files", callback)
                # On Linux we need sudo, on macOS we don't
                if self.system == "Linux":
                    subprocess.run(['sudo', 'cp', '-r', f"{iso_mount}/.", mount_point], check=True)
                elif self.system == "Darwin":
                    for item in os.listdir(iso_mount):
                        src = os.path.join(iso_mount, item)
                        dst = os.path.join(mount_point, item)
                        if os.path.isdir(src):
                            shutil.copytree(src, dst)
                        else:
                            shutil.copy2(src, dst)
                
                # Unmount everything
                self._update_progress(90, "Finalizing", callback)
                if self.system == "Linux":
                    subprocess.run(['sudo', 'umount', iso_mount], check=True)
                    subprocess.run(['sudo', 'umount', mount_point], check=True)
                elif self.system == "Darwin":
                    subprocess.run(['hdiutil', 'detach', iso_mount], check=True)
                    subprocess.run(['diskutil', 'unmount', mount_point], check=True)
                
                return True
                
            except Exception as e:
                self._update_progress(0, f"Error creating Windows bootable USB: {str(e)}", callback)
                return False
    
    def _iso9660_method(self, iso_path, target_device, callback):
        """Create bootable USB for standard ISO9660 images"""
        # For most Linux distributions, the dd method works better,
        # but for some old ISO9660 images without hybrid support,
        # we need to extract the ISO contents to a formatted drive
        
        self._update_progress(10, "Starting standard ISO9660 bootable USB creation", callback)
        
        try:
            # Format the drive with FAT32
            self._update_progress(20, "Formatting drive", callback)
            if self.system == "Linux":
                subprocess.run(['sudo', 'mkfs.vfat', '-F', '32', target_device], check=True)
            elif self.system == "Darwin":  # macOS
                device_name = target_device.split('/')[-1]
                subprocess.run(['diskutil', 'eraseDisk', 'MS-DOS', 'BOOTDISK', 'MBR', device_name], check=True)
            elif self.system == "Windows":
                # Assume target_device is already a drive letter for Windows
                subprocess.run(['format', target_device, '/fs:FAT32', '/q', '/y'], check=True)
            
            # Mount the drive
            self._update_progress(40, "Mounting drives", callback)
            if self.system == "Windows":
                # Windows automatically mounts the drive
                mount_point = target_device
                
                # Use PowerShell to mount the ISO
                mount_cmd = [
                    "powershell", 
                    "-Command", 
                    f"$mount = Mount-DiskImage -ImagePath '{iso_path}' -PassThru; "
                    f"$drive = ($mount | Get-Volume).DriveLetter; "
                    f"echo $drive;"
                ]
                result = subprocess.run(mount_cmd, capture_output=True, text=True, check=True)
                iso_mount = f"{result.stdout.strip()}:\\"
                
                # Copy files
                self._update_progress(60, "Copying files", callback)
                copy_cmd = [
                    "powershell", 
                    "-Command", 
                    f"Copy-Item -Path '{iso_mount}\\*' -Destination '{mount_point}' -Recurse -Force"
                ]
                subprocess.run(copy_cmd, check=True)
                
                # Unmount ISO
                self._update_progress(90, "Finalizing", callback)
                subprocess.run(
                    ["powershell", "-Command", f"Dismount-DiskImage -ImagePath '{iso_path}'"], 
                    check=True
                )
                
                return True
            else:
                # Handle Linux and macOS
                mount_point = "/tmp/usb_mount"
                iso_mount = "/tmp/iso_mount"
                
                if not os.path.exists(mount_point):
                    os.makedirs(mount_point)
                if not os.path.exists(iso_mount):
                    os.makedirs(iso_mount)
                
                # Mount the formatted drive and ISO
                if self.system == "Linux":
                    subprocess.run(['sudo', 'mount', target_device, mount_point], check=True)
                    subprocess.run(['sudo', 'mount', '-o', 'loop', iso_path, iso_mount], check=True)
                elif self.system == "Darwin":
                    # Find the mounted drive on macOS
                    result = subprocess.run(
                        ['diskutil', 'info', target_device.split('/')[-1]], 
                        capture_output=True, 
                        text=True, 
                        check=True
                    )
                    for line in result.stdout.splitlines():
                        if "Mount Point:" in line:
                            mount_point = line.split(":", 1)[1].strip()
                            break
                    
                    # Mount the ISO on macOS
                    result = subprocess.run(
                        ['hdiutil', 'attach', iso_path], 
                        capture_output=True, 
                        text=True, 
                        check=True
                    )
                    for line in result.stdout.splitlines():
                        if "/Volumes/" in line:
                            iso_mount = line.split(None, 2)[2].strip()
                            break
                
                # Copy files
                self._update_progress(60, "Copying files", callback)
                if self.system == "Linux":
                    subprocess.run(['sudo', 'cp', '-r', f"{iso_mount}/.", mount_point], check=True)
                elif self.system == "Darwin":
                    for item in os.listdir(iso_mount):
                        src = os.path.join(iso_mount, item)
                        dst = os.path.join(mount_point, item)
                        if os.path.isdir(src):
                            shutil.copytree(src, dst)
                        else:
                            shutil.copy2(src, dst)
                
                # Install syslinux bootloader for Linux (not needed on macOS)
                if self.system == "Linux":
                    self._update_progress(80, "Installing bootloader", callback)
                    syslinux_cmd = ['sudo', 'syslinux', '-i', target_device]
                    try:
                        subprocess.run(syslinux_cmd, check=True)
                    except:
                        # syslinux may not be installed or needed
                        pass
                
                # Unmount everything
                self._update_progress(90, "Finalizing", callback)
                if self.system == "Linux":
                    subprocess.run(['sudo', 'umount', iso_mount], check=True)
                    subprocess.run(['sudo', 'umount', mount_point], check=True)
                elif self.system == "Darwin":
                    subprocess.run(['hdiutil', 'detach', iso_mount], check=True)
                    subprocess.run(['diskutil', 'unmount', mount_point], check=True)
                
                return True
                
        except Exception as e:
            self._update_progress(0, f"Error creating ISO9660 bootable USB: {str(e)}", callback)
            return False