#!/usr/bin/env python3
# filepath: /home/utkarsh/Desktop/DiskForge/src/cli/commands.py

import os
import click
import platform
from src.core.disk_manager import DiskManager
from src.core.usb_creator import USBCreator
from src.core.safety import SafetyManager
import time
import sys
from colorama import init, Fore, Style

# Initialize colorama for cross-platform colored output
init()

# Create instances of our core classes
disk_manager = DiskManager()
usb_creator = USBCreator()
safety_manager = SafetyManager()

@click.group()
def cli():
    """DiskForge - A tool for disk operations and creating bootable USB drives."""
    pass

# Disk listing commands
@cli.group('list')
def list_group():
    """List disks and partitions."""
    pass

@list_group.command('disks')
def list_disks():
    """List all physical disks."""
    disks = disk_manager.list_physical_disks()
    
    if not disks:
        click.echo(f"{Fore.YELLOW}No physical disks found.{Style.RESET_ALL}")
        return
    
    click.echo(f"\n{Fore.GREEN}Physical Disks:{Style.RESET_ALL}")
    click.echo(f"{Fore.CYAN}{'Device':<15} {'Size':<10} {'Removable':<10} {'Model'}{Style.RESET_ALL}")
    click.echo("-" * 60)
    
    for disk in disks:
        removable = "Yes" if disk.get('removable', False) else "No"
        click.echo(f"{disk['device']:<15} {disk['size']:<10} {removable:<10} {disk.get('model', 'Unknown')}")

@list_group.command('partitions')
def list_partitions():
    """List all partitions."""
    partitions = disk_manager.list_partitions()
    
    if not partitions:
        click.echo(f"{Fore.YELLOW}No partitions found.{Style.RESET_ALL}")
        return
    
    click.echo(f"\n{Fore.GREEN}Partitions:{Style.RESET_ALL}")
    click.echo(f"{Fore.CYAN}{'Device':<15} {'Size':<10} {'Type':<10} {'Mountpoint':<20} {'Usage'}{Style.RESET_ALL}")
    click.echo("-" * 70)
    
    for part in partitions:
        # Calculate usage string
        usage = "Unknown"
        if part.get('percent_used') is not None:
            usage = f"{part['percent_used']:.1f}% used"
        
        # Format filesystem type
        fs_type = part.get('type', 'Unknown')
        if fs_type is None:
            fs_type = "Unknown"
        
        # Format mountpoint
        mountpoint = part.get('mountpoint', 'Not mounted')
        if mountpoint is None:
            mountpoint = "Not mounted"
        
        click.echo(f"{part['device']:<15} {part['size']:<10} {fs_type[:10]:<10} {mountpoint[:20]:<20} {usage}")

# Formatting command
@cli.command('format')
@click.argument('device')
@click.option('--filesystem', '-fs', default='ext4', 
              type=click.Choice(['ext4', 'fat32', 'ntfs', 'exfat']), 
              help='Filesystem type to format with')
def format_disk(device, filesystem):
    """Format a disk with the specified filesystem."""
    # Validate that device exists
    disks = disk_manager.list_physical_disks()
    partitions = disk_manager.list_partitions()
    
    valid_devices = [disk['device'] for disk in disks] + [part['device'] for part in partitions]
    
    if device not in valid_devices:
        click.echo(f"{Fore.RED}Error: Device {device} not found.{Style.RESET_ALL}")
        return
    
    # Confirm formatting
    click.echo(f"{Fore.RED}Warning: You are about to format {device} with {filesystem}.{Style.RESET_ALL}")
    click.echo(f"{Fore.RED}All data on this device will be lost!{Style.RESET_ALL}")
    
    if not click.confirm('Do you want to continue?'):
        click.echo("Format operation cancelled.")
        return
    
    click.echo(f"Formatting {device} with {filesystem}...")
    success = disk_manager.format_device(device, filesystem)
    
    if success:
        click.echo(f"{Fore.GREEN}Format completed successfully.{Style.RESET_ALL}")
    else:
        click.echo(f"{Fore.RED}Format failed. Check system logs for details.{Style.RESET_ALL}")

# Create bootable USB command
@cli.command('create-usb')
@click.argument('iso-path', type=click.Path(exists=True))
@click.argument('device')
@click.option('--method', default='auto', 
              type=click.Choice(['auto', 'dd', 'iso9660', 'hybrid', 'windows']), 
              help='Method to use for creating bootable USB')
def create_bootable_usb(iso_path, device, method):
    """Create a bootable USB drive from an ISO file."""
    # Validate that device exists
    disks = disk_manager.list_physical_disks()
    
    valid_devices = [disk['device'] for disk in disks]
    
    if device not in valid_devices:
        click.echo(f"{Fore.RED}Error: Device {device} not found.{Style.RESET_ALL}")
        return
    
    # Check that the device is removable for safety
    for disk in disks:
        if disk['device'] == device and not disk.get('removable', False):
            click.echo(f"{Fore.RED}Warning: {device} does not appear to be a removable device.{Style.RESET_ALL}")
            if not click.confirm('Are you sure you want to continue?'):
                click.echo("Operation cancelled.")
                return
    
    # Confirm operation
    click.echo(f"{Fore.YELLOW}Warning: You are about to create a bootable USB on {device}.{Style.RESET_ALL}")
    click.echo(f"{Fore.YELLOW}All data on this device will be lost!{Style.RESET_ALL}")
    
    if not click.confirm('Do you want to continue?'):
        click.echo("Operation cancelled.")
        return
    
    # Define the progress callback
    def progress_callback(progress, status):
        # Clear line and print progress
        sys.stdout.write("\r" + " " * 80)
        sys.stdout.write(f"\r{Fore.BLUE}[{progress}%] {status}{Style.RESET_ALL}")
        sys.stdout.flush()
    
    # Start the creation process
    click.echo(f"Creating bootable USB from {iso_path} on {device} using {method} method...")
    success = usb_creator.create_bootable_usb(iso_path, device, method, progress_callback)
    
    if not success:
        click.echo(f"\n{Fore.RED}Failed to start USB creation process: {usb_creator.status}{Style.RESET_ALL}")
        return
    
    # Wait for the process to finish
    try:
        while usb_creator.is_running:
            time.sleep(0.5)
        
        # Final status
        if usb_creator.progress == 100:
            click.echo(f"\n{Fore.GREEN}Bootable USB created successfully!{Style.RESET_ALL}")
        else:
            click.echo(f"\n{Fore.RED}USB creation failed: {usb_creator.status}{Style.RESET_ALL}")
    
    except KeyboardInterrupt:
        click.echo("\nCancelling operation...")
        usb_creator.cancel()
        click.echo(f"{Fore.YELLOW}Operation cancelled.{Style.RESET_ALL}")

# System information command
@cli.command('info')
def system_info():
    """Display system information."""
    click.echo(f"\n{Fore.GREEN}System Information:{Style.RESET_ALL}")
    click.echo(f"Operating System: {platform.system()} {platform.release()}")
    click.echo(f"Platform: {platform.platform()}")
    click.echo(f"Architecture: {platform.machine()}")
    
    # Display Python information
    click.echo(f"\n{Fore.GREEN}Python Information:{Style.RESET_ALL}")
    click.echo(f"Python Version: {platform.python_version()}")
    click.echo(f"Python Implementation: {platform.python_implementation()}")
    
    # Display application information
    click.echo(f"\n{Fore.GREEN}DiskForge Information:{Style.RESET_ALL}")
    click.echo(f"Version: 0.1.0")
    click.echo(f"Path: {os.path.dirname(os.path.dirname(os.path.abspath(__file__)))}")

if __name__ == '__main__':
    cli()
