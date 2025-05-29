#!/usr/bin/env python3
# filepath: /home/utkarsh/Desktop/DiskForge/src/gui/main_window.py

import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                            QWidget, QPushButton, QTableWidget, QTableWidgetItem, 
                            QTabWidget, QComboBox, QLabel, QFileDialog, QTextEdit,
                            QProgressBar, QMessageBox, QGroupBox, QCheckBox,
                            QSplitter, QFrame)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QIcon, QPalette, QColor
import threading
import time

from src.core.disk_manager import DiskManager
from src.core.usb_creator import USBCreator
from src.core.safety import SafetyManager


class OperationThread(QThread):
    """Thread for running disk operations in the background"""
    progress_updated = pyqtSignal(int, str)
    operation_finished = pyqtSignal(bool, str)
    
    def __init__(self, operation_type, *args, **kwargs):
        super().__init__()
        self.operation_type = operation_type
        self.args = args
        self.kwargs = kwargs
        self.disk_manager = DiskManager()
        self.usb_creator = USBCreator()
        
    def run(self):
        try:
            if self.operation_type == "format":
                device, filesystem = self.args
                self.progress_updated.emit(10, f"Starting format of {device}...")
                success = self.disk_manager.format_device(device, filesystem)
                self.progress_updated.emit(100, "Format completed")
                self.operation_finished.emit(success, "Format operation completed" if success else "Format failed")
                
            elif self.operation_type == "create_usb":
                iso_path, device, method = self.args
                progress_callback = self.kwargs.get('progress_callback')
                
                def thread_progress_callback(progress, status):
                    self.progress_updated.emit(progress, status)
                
                success = self.usb_creator.create_bootable_usb(iso_path, device, method, thread_progress_callback)
                if success:
                    # Wait for completion
                    while self.usb_creator.is_running:
                        time.sleep(0.1)
                    
                    if self.usb_creator.progress == 100:
                        self.operation_finished.emit(True, "Bootable USB created successfully")
                    else:
                        self.operation_finished.emit(False, f"USB creation failed: {self.usb_creator.status}")
                else:
                    self.operation_finished.emit(False, f"Failed to start USB creation: {self.usb_creator.status}")
                    
        except Exception as e:
            self.operation_finished.emit(False, f"Operation failed: {str(e)}")


class DiskForgeMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.disk_manager = DiskManager()
        self.usb_creator = USBCreator()
        self.safety_manager = SafetyManager()
        self.operation_thread = None
        
        self.init_ui()
        self.setup_refresh_timer()
        self.refresh_disk_info()
        
    def init_ui(self):
        self.setWindowTitle("DiskForge - Disk Management Tool")
        self.setGeometry(100, 100, 1000, 700)
        
        # Set application style
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f0f0;
            }
            QTabWidget::pane {
                border: 1px solid #c0c0c0;
                background-color: white;
            }
            QTabBar::tab {
                background-color: #e0e0e0;
                padding: 8px 16px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: white;
                border-bottom: 2px solid #0078d4;
            }
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
            QTableWidget {
                gridline-color: #d0d0d0;
                background-color: white;
                alternate-background-color: #f8f8f8;
            }
            QTableWidget::item {
                padding: 4px;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #c0c0c0;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
            }
        """)
        
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # Create tabs
        self.create_disk_info_tab()
        self.create_format_tab()
        self.create_usb_creator_tab()
        self.create_system_info_tab()
        
        # Status bar
        self.statusBar().showMessage("Ready")
        
    def create_disk_info_tab(self):
        """Create the disk information tab"""
        disk_tab = QWidget()
        layout = QVBoxLayout(disk_tab)
        
        # Refresh button
        refresh_layout = QHBoxLayout()
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.refresh_disk_info)
        refresh_layout.addWidget(refresh_btn)
        refresh_layout.addStretch()
        layout.addLayout(refresh_layout)
        
        # Splitter for disks and partitions
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)
        
        # Physical disks group
        disks_group = QGroupBox("Physical Disks")
        disks_layout = QVBoxLayout(disks_group)
        
        self.disks_table = QTableWidget()
        self.disks_table.setColumnCount(4)
        self.disks_table.setHorizontalHeaderLabels(["Device", "Size", "Removable", "Model"])
        self.disks_table.setAlternatingRowColors(True)
        self.disks_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        disks_layout.addWidget(self.disks_table)
        
        splitter.addWidget(disks_group)
        
        # Partitions group
        partitions_group = QGroupBox("Partitions")
        partitions_layout = QVBoxLayout(partitions_group)
        
        self.partitions_table = QTableWidget()
        self.partitions_table.setColumnCount(5)
        self.partitions_table.setHorizontalHeaderLabels(["Device", "Size", "Type", "Mountpoint", "Usage"])
        self.partitions_table.setAlternatingRowColors(True)
        self.partitions_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        partitions_layout.addWidget(self.partitions_table)
        
        splitter.addWidget(partitions_group)
        
        self.tab_widget.addTab(disk_tab, "📀 Disk Information")
        
    def create_format_tab(self):
        """Create the format disk tab"""
        format_tab = QWidget()
        layout = QVBoxLayout(format_tab)
        
        # Format options group
        format_group = QGroupBox("Format Device")
        format_layout = QVBoxLayout(format_group)
        
        # Device selection
        device_layout = QHBoxLayout()
        device_layout.addWidget(QLabel("Device:"))
        self.format_device_combo = QComboBox()
        device_layout.addWidget(self.format_device_combo)
        device_layout.addStretch()
        format_layout.addLayout(device_layout)
        
        # Filesystem selection
        fs_layout = QHBoxLayout()
        fs_layout.addWidget(QLabel("Filesystem:"))
        self.filesystem_combo = QComboBox()
        self.filesystem_combo.addItems(["ext4", "fat32", "ntfs", "exfat"])
        fs_layout.addWidget(self.filesystem_combo)
        fs_layout.addStretch()
        format_layout.addLayout(fs_layout)
        
        # Safety checkbox
        self.format_confirm_checkbox = QCheckBox("I understand this will erase all data")
        format_layout.addWidget(self.format_confirm_checkbox)
        
        # Format button
        self.format_btn = QPushButton("🗑️ Format Device")
        self.format_btn.clicked.connect(self.format_device)
        self.format_btn.setEnabled(False)
        self.format_confirm_checkbox.toggled.connect(lambda checked: self.format_btn.setEnabled(checked))
        format_layout.addWidget(self.format_btn)
        
        layout.addWidget(format_group)
        
        # Progress group
        progress_group = QGroupBox("Operation Progress")
        progress_layout = QVBoxLayout(progress_group)
        
        self.format_progress = QProgressBar()
        progress_layout.addWidget(self.format_progress)
        
        self.format_status_label = QLabel("Ready")
        progress_layout.addWidget(self.format_status_label)
        
        layout.addWidget(progress_group)
        layout.addStretch()
        
        self.tab_widget.addTab(format_tab, "💿 Format")
        
    def create_usb_creator_tab(self):
        """Create the USB creator tab"""
        usb_tab = QWidget()
        layout = QVBoxLayout(usb_tab)
        
        # USB creation options group
        usb_group = QGroupBox("Create Bootable USB")
        usb_layout = QVBoxLayout(usb_group)
        
        # ISO file selection
        iso_layout = QHBoxLayout()
        iso_layout.addWidget(QLabel("ISO File:"))
        self.iso_path_label = QLabel("No file selected")
        self.iso_path_label.setStyleSheet("padding: 4px; border: 1px solid #ccc; background-color: white;")
        iso_layout.addWidget(self.iso_path_label)
        
        browse_btn = QPushButton("📁 Browse")
        browse_btn.clicked.connect(self.browse_iso_file)
        iso_layout.addWidget(browse_btn)
        usb_layout.addLayout(iso_layout)
        
        # Target device selection
        device_layout = QHBoxLayout()
        device_layout.addWidget(QLabel("Target Device:"))
        self.usb_device_combo = QComboBox()
        device_layout.addWidget(self.usb_device_combo)
        device_layout.addStretch()
        usb_layout.addLayout(device_layout)
        
        # Method selection
        method_layout = QHBoxLayout()
        method_layout.addWidget(QLabel("Method:"))
        self.method_combo = QComboBox()
        self.method_combo.addItems(["auto", "dd", "iso9660", "hybrid", "windows"])
        method_layout.addWidget(self.method_combo)
        method_layout.addStretch()
        usb_layout.addLayout(method_layout)
        
        # Safety checkbox
        self.usb_confirm_checkbox = QCheckBox("I understand this will erase all data on the target device")
        usb_layout.addWidget(self.usb_confirm_checkbox)
        
        # Create USB button
        self.create_usb_btn = QPushButton("🚀 Create Bootable USB")
        self.create_usb_btn.clicked.connect(self.create_bootable_usb)
        self.create_usb_btn.setEnabled(False)
        self.usb_confirm_checkbox.toggled.connect(self.update_usb_button_state)
        usb_layout.addWidget(self.create_usb_btn)
        
        layout.addWidget(usb_group)
        
        # Progress group
        progress_group = QGroupBox("Creation Progress")
        progress_layout = QVBoxLayout(progress_group)
        
        self.usb_progress = QProgressBar()
        progress_layout.addWidget(self.usb_progress)
        
        self.usb_status_label = QLabel("Ready")
        progress_layout.addWidget(self.usb_status_label)
        
        # Cancel button
        self.cancel_usb_btn = QPushButton("❌ Cancel")
        self.cancel_usb_btn.clicked.connect(self.cancel_usb_creation)
        self.cancel_usb_btn.setEnabled(False)
        progress_layout.addWidget(self.cancel_usb_btn)
        
        layout.addWidget(progress_group)
        layout.addStretch()
        
        self.tab_widget.addTab(usb_tab, "💾 USB Creator")
        
    def create_system_info_tab(self):
        """Create the system information tab"""
        info_tab = QWidget()
        layout = QVBoxLayout(info_tab)
        
        # System info text area
        self.system_info_text = QTextEdit()
        self.system_info_text.setReadOnly(True)
        self.system_info_text.setFont(QFont("Consolas", 10))
        layout.addWidget(self.system_info_text)
        
        # Refresh button
        refresh_info_btn = QPushButton("🔄 Refresh System Info")
        refresh_info_btn.clicked.connect(self.refresh_system_info)
        layout.addWidget(refresh_info_btn)
        
        self.tab_widget.addTab(info_tab, "ℹ️ System Info")
        
    def setup_refresh_timer(self):
        """Setup timer for automatic refresh"""
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_disk_info)
        self.refresh_timer.start(5000)  # Refresh every 5 seconds
        
    def refresh_disk_info(self):
        """Refresh disk and partition information"""
        try:
            # Refresh physical disks
            disks = self.disk_manager.list_physical_disks()
            self.update_disks_table(disks)
            
            # Refresh partitions
            partitions = self.disk_manager.list_partitions()
            self.update_partitions_table(partitions)
            
            # Update device combo boxes
            self.update_device_combos(disks)
            
            self.statusBar().showMessage(f"Last updated: {time.strftime('%H:%M:%S')}")
            
        except Exception as e:
            self.statusBar().showMessage(f"Error refreshing disk info: {str(e)}")
            
    def update_disks_table(self, disks):
        """Update the physical disks table"""
        self.disks_table.setRowCount(len(disks))
        
        for row, disk in enumerate(disks):
            self.disks_table.setItem(row, 0, QTableWidgetItem(disk['device']))
            self.disks_table.setItem(row, 1, QTableWidgetItem(disk['size']))
            self.disks_table.setItem(row, 2, QTableWidgetItem("Yes" if disk.get('removable', False) else "No"))
            self.disks_table.setItem(row, 3, QTableWidgetItem(disk.get('model', 'Unknown')))
            
        self.disks_table.resizeColumnsToContents()
        
    def update_partitions_table(self, partitions):
        """Update the partitions table"""
        self.partitions_table.setRowCount(len(partitions))
        
        for row, part in enumerate(partitions):
            self.partitions_table.setItem(row, 0, QTableWidgetItem(part['device']))
            self.partitions_table.setItem(row, 1, QTableWidgetItem(part['size']))
            
            fs_type = part.get('type', 'Unknown')
            if fs_type is None:
                fs_type = "Unknown"
            self.partitions_table.setItem(row, 2, QTableWidgetItem(fs_type))
            
            mountpoint = part.get('mountpoint', 'Not mounted')
            if mountpoint is None:
                mountpoint = "Not mounted"
            self.partitions_table.setItem(row, 3, QTableWidgetItem(mountpoint))
            
            usage = "Unknown"
            if part.get('percent_used') is not None:
                usage = f"{part['percent_used']:.1f}% used"
            self.partitions_table.setItem(row, 4, QTableWidgetItem(usage))
            
        self.partitions_table.resizeColumnsToContents()
        
    def update_device_combos(self, disks):
        """Update device combo boxes"""
        # Save current selections
        current_format_device = self.format_device_combo.currentText()
        current_usb_device = self.usb_device_combo.currentText()
        
        # Clear and repopulate
        self.format_device_combo.clear()
        self.usb_device_combo.clear()
        
        # Add all devices to format combo
        partitions = self.disk_manager.list_partitions()
        all_devices = [disk['device'] for disk in disks] + [part['device'] for part in partitions]
        self.format_device_combo.addItems(all_devices)
        
        # Add only removable devices to USB combo
        removable_devices = [disk['device'] for disk in disks if disk.get('removable', False)]
        self.usb_device_combo.addItems(removable_devices)
        
        # Restore selections if still valid
        if current_format_device in all_devices:
            self.format_device_combo.setCurrentText(current_format_device)
        if current_usb_device in removable_devices:
            self.usb_device_combo.setCurrentText(current_usb_device)
            
    def update_usb_button_state(self):
        """Update USB creation button state"""
        has_iso = self.iso_path_label.text() != "No file selected"
        has_device = self.usb_device_combo.currentText() != ""
        confirmed = self.usb_confirm_checkbox.isChecked()
        not_running = self.operation_thread is None or not self.operation_thread.isRunning()
        
        self.create_usb_btn.setEnabled(has_iso and has_device and confirmed and not_running)
        
    def browse_iso_file(self):
        """Browse for ISO file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select ISO File", "", "ISO Files (*.iso);;All Files (*)"
        )
        
        if file_path:
            self.iso_path_label.setText(file_path)
            self.update_usb_button_state()
            
    def format_device(self):
        """Format the selected device"""
        device = self.format_device_combo.currentText()
        filesystem = self.filesystem_combo.currentText()
        
        if not device:
            QMessageBox.warning(self, "Warning", "Please select a device to format.")
            return
            
        # Safety check
        if not self.safety_manager.is_safe_device(device):
            reply = QMessageBox.question(
                self, "Dangerous Operation",
                f"Warning: {device} appears to be a system device!\n"
                "Formatting this device could make your system unbootable.\n"
                "Are you absolutely sure you want to continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
                
        # Final confirmation
        reply = QMessageBox.question(
            self, "Confirm Format",
            f"Are you sure you want to format {device} with {filesystem}?\n"
            "This will permanently delete all data on the device!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.start_format_operation(device, filesystem)
            
    def start_format_operation(self, device, filesystem):
        """Start format operation in background thread"""
        self.format_btn.setEnabled(False)
        self.format_progress.setValue(0)
        self.format_status_label.setText(f"Formatting {device}...")
        
        self.operation_thread = OperationThread("format", device, filesystem)
        self.operation_thread.progress_updated.connect(self.update_format_progress)
        self.operation_thread.operation_finished.connect(self.format_operation_finished)
        self.operation_thread.start()
        
    def update_format_progress(self, progress, status):
        """Update format progress"""
        self.format_progress.setValue(progress)
        self.format_status_label.setText(status)
        
    def format_operation_finished(self, success, message):
        """Handle format operation completion"""
        self.format_btn.setEnabled(True)
        
        if success:
            QMessageBox.information(self, "Success", message)
            self.format_progress.setValue(100)
            self.format_status_label.setText("Format completed successfully")
        else:
            QMessageBox.critical(self, "Error", message)
            self.format_status_label.setText("Format failed")
            
        self.refresh_disk_info()
        
    def create_bootable_usb(self):
        """Create bootable USB"""
        iso_path = self.iso_path_label.text()
        device = self.usb_device_combo.currentText()
        method = self.method_combo.currentText()
        
        if iso_path == "No file selected":
            QMessageBox.warning(self, "Warning", "Please select an ISO file.")
            return
            
        if not device:
            QMessageBox.warning(self, "Warning", "Please select a target device.")
            return
            
        # Final confirmation
        reply = QMessageBox.question(
            self, "Confirm USB Creation",
            f"Are you sure you want to create a bootable USB on {device}?\n"
            f"Using ISO: {os.path.basename(iso_path)}\n"
            "This will permanently delete all data on the device!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.start_usb_creation(iso_path, device, method)
            
    def start_usb_creation(self, iso_path, device, method):
        """Start USB creation in background thread"""
        self.create_usb_btn.setEnabled(False)
        self.cancel_usb_btn.setEnabled(True)
        self.usb_progress.setValue(0)
        self.usb_status_label.setText("Starting USB creation...")
        
        self.operation_thread = OperationThread("create_usb", iso_path, device, method)
        self.operation_thread.progress_updated.connect(self.update_usb_progress)
        self.operation_thread.operation_finished.connect(self.usb_operation_finished)
        self.operation_thread.start()
        
    def update_usb_progress(self, progress, status):
        """Update USB creation progress"""
        self.usb_progress.setValue(progress)
        self.usb_status_label.setText(status)
        
    def usb_operation_finished(self, success, message):
        """Handle USB creation completion"""
        self.create_usb_btn.setEnabled(True)
        self.cancel_usb_btn.setEnabled(False)
        self.update_usb_button_state()
        
        if success:
            QMessageBox.information(self, "Success", message)
            self.usb_progress.setValue(100)
            self.usb_status_label.setText("USB creation completed successfully")
        else:
            QMessageBox.critical(self, "Error", message)
            self.usb_status_label.setText("USB creation failed")
            
    def cancel_usb_creation(self):
        """Cancel USB creation"""
        if self.usb_creator.is_running:
            self.usb_creator.cancel()
            self.usb_status_label.setText("Cancelling operation...")
            
    def refresh_system_info(self):
        """Refresh system information"""
        import platform
        
        info_text = f"""System Information:
Operating System: {platform.system()} {platform.release()}
Platform: {platform.platform()}
Architecture: {platform.machine()}
Processor: {platform.processor()}

Python Information:
Python Version: {platform.python_version()}
Python Implementation: {platform.python_implementation()}

DiskForge Information:
Version: 0.1.0
Path: {os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))}

Available Disk Operations:
- List physical disks and partitions
- Format devices with various filesystems
- Create bootable USB drives
- Real-time disk monitoring
"""
        
        self.system_info_text.setPlainText(info_text)
        
    def closeEvent(self, event):
        """Handle application close"""
        if self.operation_thread and self.operation_thread.isRunning():
            reply = QMessageBox.question(
                self, "Confirm Exit",
                "An operation is currently running. Are you sure you want to exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                if self.usb_creator.is_running:
                    self.usb_creator.cancel()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


def run_gui():
    """Run the GUI application"""
    app = QApplication(sys.argv)
    app.setApplicationName("DiskForge")
    app.setApplicationVersion("0.1.0")
    
    # Set application icon (if available)
    # app.setWindowIcon(QIcon("assets/icon.png"))
    
    window = DiskForgeMainWindow()
    window.show()
    
    # Load system info on startup
    window.refresh_system_info()
    
    return app.exec()


if __name__ == "__main__":
    sys.exit(run_gui())