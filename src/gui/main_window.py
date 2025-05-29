#!/usr/bin/env python3
# filepath: /home/utkarsh/Desktop/DiskForge/src/gui/main_window.py

import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                            QWidget, QPushButton, QTableWidget, QTableWidgetItem, 
                            QTabWidget, QComboBox, QLabel, QFileDialog, QTextEdit,
                            QProgressBar, QMessageBox, QGroupBox, QCheckBox,
                            QSplitter, QFrame, QStyledItemDelegate, QStyle, QStyleOptionViewItem)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QIcon, QPalette, QColor, QBrush
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
        self.refresh_timer = None
        
        self.init_ui()
        self.setup_refresh_timer()
        self.refresh_disk_info()
        
    def get_friendly_device_name(self, device_path, device_info=None):
        """
        Generate a user-friendly name for a device based on its properties
        
        Args:
            device_path: The technical device path (e.g., /dev/sda)
            device_info: Optional dictionary with device details
            
        Returns:
            A user-friendly device name
        """
        if not device_info:
            return os.path.basename(device_path)
            
        # Start with model if available
        friendly_name = device_info.get('model', '')
        
        # If no model, try to create a descriptive name
        if not friendly_name or friendly_name == 'Unknown':
            device_name = os.path.basename(device_path)
            size = device_info.get('size', '')
            
            if device_info.get('removable', False):
                friendly_name = f"Removable Drive ({size})"
            elif self.safety_manager.is_system_drive(device_path):
                friendly_name = f"System Drive ({size})"
            else:
                friendly_name = f"Storage Drive ({size})"
                
            # Add device name for technical reference
            friendly_name += f" [{device_name}]"
        else:
            # Add size information to model name
            size = device_info.get('size', '')
            if size:
                friendly_name += f" ({size})"
                
        return friendly_name
        
    def get_device_status(self, device_path):
        """
        Generate a status description for a device based on its properties
        
        Args:
            device_path: The device path to check
            
        Returns:
            A status string describing the device
        """
        status = []
        
        # Check if it's a system drive
        if self.safety_manager.is_system_drive(device_path):
            status.append("System Drive")
        
        # Check if it's currently mounted
        for part in self.safety_manager.get_device_info(device_path).get('mounted_partitions', []):
            if part.get('mountpoint') == '/':
                status.append("Root Partition")
                break
        else:
            # Check if it contains mounted partitions
            if self.safety_manager.get_device_info(device_path).get('mounted_partitions'):
                status.append("Has Mounted Partitions")
        
        # Check if it's removable
        disks = self.disk_manager.list_physical_disks()
        for disk in disks:
            if disk['device'] == device_path and disk.get('removable'):
                status.append("Removable Device")
                break
                
        # If we have no status, it's likely just a regular storage device
        if not status:
            status.append("Storage Device")
            
        return ", ".join(status)
    
    class DeviceItemDelegate(QStyledItemDelegate):
        """Custom delegate for better device display in combo boxes"""
        
        def __init__(self, parent=None, safety_manager=None):
            super().__init__(parent)
            self.safety_manager = safety_manager
            
        def paint(self, painter, option, index):
            """Custom painting for device entries with safety indicators"""
            if not index.isValid():
                return super().paint(painter, option, index)
                
            # Get the device path from the item data
            device_path = index.data(Qt.ItemDataRole.UserRole)
            if not device_path:
                return super().paint(painter, option, index)
                
            # Prepare the style option
            opt = QStyleOptionViewItem(option)
            self.initStyleOption(opt, index)
            
            # Check if it's a system drive and adjust background accordingly
            if self.safety_manager and not self.safety_manager.is_safe_device(device_path):
                # System drives get a light red background
                opt.backgroundBrush = QBrush(QColor("#fadbd8"))
            else:
                # Check if it's a removable device
                is_removable = False
                device_info = index.data(Qt.ItemDataRole.UserRole + 1)
                if isinstance(device_info, dict) and device_info.get('removable', False):
                    # Removable devices get a light green background
                    is_removable = True
                    opt.backgroundBrush = QBrush(QColor("#d4efdf"))
            
            # Draw the item with our custom styling
            QApplication.style().drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter)
    
    def init_ui(self):
        self.setWindowTitle("DiskForge - Disk Management Tool")
        self.setGeometry(100, 100, 1000, 700)
        
        # Set application style with enhanced colors
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f4f8;
            }
            QTabWidget::pane {
                border: 1px solid #c0c0c0;
                background-color: white;
                border-radius: 6px;
                box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
            }
            QTabBar::tab {
                background-color: #e3e8f0;
                color: #444444;
                padding: 12px 24px;
                margin-right: 3px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background-color: #0078d4;
                color: white;
                border-bottom: none;
                box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
            }
            QTabBar::tab:hover:!selected {
                background-color: #d0d8e8;
            }
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 6px;
                font-weight: bold;
                min-height: 32px;
                box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            }
            QPushButton:hover {
                background-color: #0086f0;
                box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2);
            }
            QPushButton:pressed {
                background-color: #005a9e;
                box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.2);
            }
            QPushButton:disabled {
                background-color: #d0d0d0;
                color: #707070;
                box-shadow: none;
            }
            
            /* Danger buttons - for format operations */
            QPushButton#dangerButton {
                background-color: #e74c3c;
                border: 1px solid #c0392b;
            }
            QPushButton#dangerButton:hover {
                background-color: #ff5a4c;
                border: 1px solid #e74c3c;
            }
            QPushButton#dangerButton:pressed {
                background-color: #c0392b;
                border: 1px solid #a93226;
            }
            QPushButton#dangerButton:disabled {
                background-color: #f8d0c8;
                border: 1px solid #e0b8b8;
                color: #a06060;
            }
            
            /* Success buttons - for safe operations */
            QPushButton#successButton {
                background-color: #2ecc71;
                border: 1px solid #27ae60;
            }
            QPushButton#successButton:hover {
                background-color: #3ee683;
                border: 1px solid #2ecc71;
            }
            QPushButton#successButton:pressed {
                background-color: #27ae60;
                border: 1px solid #1e8449;
            }
            QPushButton#successButton:disabled {
                background-color: #c8e8d0;
                border: 1px solid #b8e0b8;
                color: #609460;
            }
            
            QTableWidget {
                gridline-color: #e0e0e8;
                background-color: white;
                alternate-background-color: #f2f8ff;
                border: 1px solid #c0c8d8;
                border-radius: 6px;
                margin: 5px;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #e8e8f0;
            }
            QTableWidget::item:selected {
                background-color: #0078d4;
                color: white;
            }
            QHeaderView::section {
                background-color: #daeaff;
                color: #222222;
                font-weight: bold;
                padding: 10px 8px;
                border: none;
                border-bottom: 2px solid #0078d4;
                border-right: 1px solid #c0d0e8;
            }
            
            QGroupBox {
                font-weight: bold;
                border: 2px solid #c0c0c0;
                border-radius: 8px;
                margin-top: 16px;
                padding-top: 12px;
                background-color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px;
                color: #0078d4;
            }
            
            QLabel {
                color: #333333;
            }
            
            QLabel#diskInfoLabel {
                font-weight: bold;
                color: #0078d4;
            }
            
            QComboBox {
                border: 1px solid #c0c8d8;
                border-radius: 5px;
                padding: 8px;
                background-color: white;
                min-height: 30px;
                selection-background-color: #0078d4;
                selection-color: white;
            }
            
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left: 1px solid #c0c8d8;
                border-top-right-radius: 5px;
                border-bottom-right-radius: 5px;
            }
            
            QComboBox::down-arrow {
                width: 16px;
                height: 16px;
                image: url(./assets/dropdown_arrow.png);
            }
            
            QComboBox QAbstractItemView {
                border: 1px solid #c0c8d8;
                selection-background-color: #0078d4;
                outline: 0;
            }
            
            QProgressBar {
                border: 1px solid #c0c0c0;
                border-radius: 4px;
                background-color: #f0f0f0;
                text-align: center;
                padding: 1px;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #0078d4;
                width: 1px;
                margin: 0px;
            }
            
            QCheckBox {
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QCheckBox::indicator:unchecked {
                border: 2px solid #c0c0c0;
                background-color: white;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                border: 2px solid #0078d4;
                background-color: #0078d4;
                border-radius: 3px;
            }
            
            /* System drive warning styles */
            QLabel#warningLabel {
                color: #e74c3c;
                font-weight: bold;
                background-color: #ffeceb;
                border: 1px solid #ffd0c8;
                border-radius: 4px;
                padding: 8px;
            }
            
            /* Removable drive indicator */
            QLabel#removableLabel {
                color: #27ae60;
                font-weight: bold;
                background-color: #e8f8f0;
                border: 1px solid #c8e8d0;
                border-radius: 4px;
                padding: 8px;
            }
            
            /* Info label */
            QLabel#infoLabel {
                color: #2980b9;
                background-color: #e8f4fa;
                border: 1px solid #c8e0f0;
                border-radius: 4px;
                padding: 8px;
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
        
        # Setup custom device view
        self.setup_custom_device_view()
        
        # Status bar
        self.statusBar().showMessage("Ready")
        
    def create_disk_info_tab(self):
        """Create the disk information tab with enhanced user-friendly display"""
        disk_tab = QWidget()
        layout = QVBoxLayout(disk_tab)
        
        # Intro label with explanation
        intro_label = QLabel(
            "This tab shows all storage devices connected to your computer. "
            "Removable devices (like USB drives) are shown with a green 'YES' indicator. "
            "System drives (containing your operating system) are highlighted for safety."
        )
        intro_label.setWordWrap(True)
        intro_label.setStyleSheet("color: #555555; padding: 10px; background-color: #f9f9f9; border-radius: 4px;")
        layout.addWidget(intro_label)
        
        # Refresh button
        refresh_layout = QHBoxLayout()
        refresh_btn = QPushButton("🔄 Refresh Devices")
        refresh_btn.clicked.connect(self.refresh_disk_info)
        refresh_layout.addWidget(refresh_btn)
        
        # Auto-refresh option
        self.auto_refresh_checkbox = QCheckBox("Auto-refresh every 5 seconds")
        self.auto_refresh_checkbox.setChecked(True)
        self.auto_refresh_checkbox.toggled.connect(self.toggle_auto_refresh)
        refresh_layout.addWidget(self.auto_refresh_checkbox)
        
        refresh_layout.addStretch()
        layout.addLayout(refresh_layout)
        
        # Splitter for disks and partitions
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter, 1)  # Give it stretch factor for proper sizing
        
        # Physical disks group with enhanced information
        disks_group = QGroupBox("Physical Storage Devices")
        disks_layout = QVBoxLayout(disks_group)
        
        self.disks_table = QTableWidget()
        self.disks_table.setColumnCount(6)  # Added more columns for better identification
        self.disks_table.setHorizontalHeaderLabels(["Device", "Friendly Name", "Size", "Removable", "Model/Brand", "Status"])
        self.disks_table.setAlternatingRowColors(True)
        self.disks_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.disks_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.disks_table.horizontalHeader().setStretchLastSection(True)
        disks_layout.addWidget(self.disks_table)
        
        # Connect selection signal to show more details
        self.disks_table.itemSelectionChanged.connect(self.show_disk_details)
        
        # Disk details section
        disk_details_label = QLabel("Device Details:")
        disk_details_label.setObjectName("diskInfoLabel")
        disks_layout.addWidget(disk_details_label)
        
        self.disk_details_text = QTextEdit()
        self.disk_details_text.setReadOnly(True)
        self.disk_details_text.setMaximumHeight(100)
        self.disk_details_text.setStyleSheet("background-color: #fafafa; border: 1px solid #ddd;")
        disks_layout.addWidget(self.disk_details_text)
        
        splitter.addWidget(disks_group)
        
        # Partitions group with enhanced information
        partitions_group = QGroupBox("Partitions / Volumes")
        partitions_layout = QVBoxLayout(partitions_group)
        
        self.partitions_table = QTableWidget()
        self.partitions_table.setColumnCount(6)
        self.partitions_table.setHorizontalHeaderLabels(["Device", "Label/Name", "Size", "Type", "Mount Location", "Usage"])
        self.partitions_table.setAlternatingRowColors(True)
        self.partitions_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.partitions_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.partitions_table.horizontalHeader().setStretchLastSection(True)
        partitions_layout.addWidget(self.partitions_table)
        
        # Safety information
        safety_label = QLabel(
            "⚠️ Safety Warning: System drives (containing your operating system) are critical "
            "for your computer to function. Be extremely careful when selecting devices for formatting."
        )
        safety_label.setWordWrap(True)
        safety_label.setStyleSheet("color: #e74c3c; padding: 5px; font-weight: bold; background-color: #fadbd8; border-radius: 4px;")
        partitions_layout.addWidget(safety_label)
        
        splitter.addWidget(partitions_group)
        
        # Set equal widths
        splitter.setSizes([500, 500])
        
        self.tab_widget.addTab(disk_tab, "📀 Disk Information")
        
    def create_format_tab(self):
        """Create the format disk tab with enhanced UI"""
        format_tab = QWidget()
        layout = QVBoxLayout(format_tab)
        
        # Warning information at the top
        warning_box = QFrame()
        warning_box.setStyleSheet("background-color: #fff3cd; border-radius: 5px; padding: 5px;")
        warning_layout = QHBoxLayout(warning_box)
        
        warning_icon = QLabel("⚠️")
        warning_icon.setStyleSheet("font-size: 24px; padding: 5px;")
        warning_layout.addWidget(warning_icon)
        
        warning_text = QLabel(
            "<b>Warning:</b> Formatting will permanently erase ALL data on the selected device. "
            "Make sure you have backed up any important data before proceeding."
        )
        warning_text.setWordWrap(True)
        warning_text.setStyleSheet("color: #856404; font-size: 12px;")
        warning_layout.addWidget(warning_text)
        
        layout.addWidget(warning_box)
        
        # Format options group with improved layout
        format_group = QGroupBox("Format Device")
        format_layout = QVBoxLayout(format_group)
        
        # Device selection with better naming
        device_layout = QHBoxLayout()
        device_layout.addWidget(QLabel("Select Device to Format:"))
        
        self.format_device_combo = QComboBox()
        self.format_device_combo.setMinimumWidth(300)
        self.format_device_combo.currentIndexChanged.connect(self.update_format_device_info)
        device_layout.addWidget(self.format_device_combo)
        device_layout.addStretch()
        format_layout.addLayout(device_layout)
        
        # Device info display
        self.format_device_info = QLabel("Select a device to see information")
        self.format_device_info.setStyleSheet("padding: 10px; background-color: #f8f9fa; border-radius: 4px; margin: 5px 0;")
        self.format_device_info.setWordWrap(True)
        format_layout.addWidget(self.format_device_info)
        
        # Filesystem selection with descriptions
        fs_group = QGroupBox("Select Filesystem Type")
        fs_layout = QVBoxLayout(fs_group)
        
        # Description of filesystem types
        fs_description = QLabel(
            "Different filesystems are compatible with different operating systems:\n"
            "• <b>ext4</b>: Best for Linux systems only\n"
            "• <b>NTFS</b>: Compatible with Windows, read-only on Mac\n"
            "• <b>FAT32</b>: Works on all systems but limited to 4GB file size\n"
            "• <b>exFAT</b>: Compatible with all modern systems, best for external drives"
        )
        fs_description.setStyleSheet("color: #555555; padding: 5px;")
        fs_description.setWordWrap(True)
        fs_layout.addWidget(fs_description)
        
        self.filesystem_combo = QComboBox()
        self.filesystem_combo.addItems(["exFAT", "FAT32", "NTFS", "ext4"])
        fs_layout.addWidget(self.filesystem_combo)
        format_layout.addWidget(fs_group)
        
        # Safety checkboxes - requiring two confirmations for extra safety
        safety_frame = QFrame()
        safety_frame.setStyleSheet("background-color: #f8d7da; padding: 10px; border-radius: 5px; margin: 5px 0;")
        safety_layout = QVBoxLayout(safety_frame)
        
        safety_layout.addWidget(QLabel("<b>Safety Confirmation:</b>"))
        self.format_confirm_checkbox1 = QCheckBox("I have backed up any important data on this device")
        self.format_confirm_checkbox2 = QCheckBox("I understand all data on this device will be permanently erased")
        
        safety_layout.addWidget(self.format_confirm_checkbox1)
        safety_layout.addWidget(self.format_confirm_checkbox2)
        
        format_layout.addWidget(safety_frame)
        
        # Format button
        self.format_btn = QPushButton("🗑️ Format Device")
        self.format_btn.setObjectName("dangerButton")
        self.format_btn.clicked.connect(self.format_device)
        self.format_btn.setEnabled(False)
        
        # Enable button only when both checkboxes are checked
        def update_button_state():
            self.format_btn.setEnabled(
                self.format_confirm_checkbox1.isChecked() and 
                self.format_confirm_checkbox2.isChecked()
            )
            
        self.format_confirm_checkbox1.toggled.connect(update_button_state)
        self.format_confirm_checkbox2.toggled.connect(update_button_state)
        
        format_layout.addWidget(self.format_btn)
        
        layout.addWidget(format_group)
        
        # Progress group with better styling
        progress_group = QGroupBox("Operation Progress")
        progress_layout = QVBoxLayout(progress_group)
        
        self.format_progress = QProgressBar()
        self.format_progress.setStyleSheet("""
            QProgressBar {
                text-align: center;
                border: 1px solid #bbb;
                border-radius: 4px;
                background-color: #f0f0f0;
                height: 24px;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 2px;
            }
        """)
        progress_layout.addWidget(self.format_progress)
        
        self.format_status_label = QLabel("Ready")
        self.format_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.format_status_label.setStyleSheet("padding: 5px; font-weight: bold;")
        progress_layout.addWidget(self.format_status_label)
        
        layout.addWidget(progress_group)
        layout.addStretch()
        
        self.tab_widget.addTab(format_tab, "💿 Format")
    
    def create_usb_creator_tab(self):
        """Create the USB creator tab with enhanced user-friendly UI"""
        usb_tab = QWidget()
        layout = QVBoxLayout(usb_tab)
        
        # Info box at the top
        info_box = QFrame()
        info_box.setStyleSheet("background-color: #d1ecf1; border-radius: 5px; padding: 5px;")
        info_layout = QHBoxLayout(info_box)
        
        info_icon = QLabel("ℹ️")
        info_icon.setStyleSheet("font-size: 24px; padding: 5px;")
        info_layout.addWidget(info_icon)
        
        info_text = QLabel(
            "<b>About Bootable USB Drives:</b> Create a bootable USB drive from a Linux distribution ISO file. "
            "This is useful for installing Linux on a computer or running a live environment without installation. "
            "The process will erase all data on the selected USB drive."
        )
        info_text.setWordWrap(True)
        info_text.setStyleSheet("color: #0c5460; font-size: 12px;")
        info_layout.addWidget(info_text)
        
        layout.addWidget(info_box)
        
        # USB creation options group with improved layout
        usb_group = QGroupBox("Create Bootable USB Drive")
        usb_layout = QVBoxLayout(usb_group)
        
        # Step 1: ISO file selection
        step1_label = QLabel("Step 1: Select Linux ISO File")
        step1_label.setStyleSheet("font-weight: bold; color: #0078d4; margin-top: 10px;")
        usb_layout.addWidget(step1_label)
        
        iso_layout = QHBoxLayout()
        iso_layout.addWidget(QLabel("ISO File:"))
        self.iso_path_label = QLabel("No file selected")
        self.iso_path_label.setStyleSheet("padding: 8px; border: 1px solid #ccc; background-color: white; border-radius: 4px;")
        self.iso_path_label.setWordWrap(True)
        iso_layout.addWidget(self.iso_path_label, 1)  # Give it stretch factor
        
        browse_btn = QPushButton("📁 Browse")
        browse_btn.clicked.connect(self.browse_iso_file)
        iso_layout.addWidget(browse_btn)
        usb_layout.addLayout(iso_layout)
        
        # ISO info display
        self.iso_info_label = QLabel("Select an ISO file to see details")
        self.iso_info_label.setWordWrap(True)
        self.iso_info_label.setStyleSheet("color: #555; padding: 5px; font-style: italic;")
        usb_layout.addWidget(self.iso_info_label)
        
        # Step 2: Target device selection
        step2_label = QLabel("Step 2: Select Target USB Drive")
        step2_label.setStyleSheet("font-weight: bold; color: #0078d4; margin-top: 10px;")
        usb_layout.addWidget(step2_label)
        
        # USB Drive selection with custom formatting
        device_layout = QHBoxLayout()
        device_layout.addWidget(QLabel("USB Drive:"))
        self.usb_device_combo = QComboBox()
        self.usb_device_combo.currentIndexChanged.connect(self.update_usb_device_info)
        device_layout.addWidget(self.usb_device_combo, 1)  # Give it stretch factor
        
        # Refresh USB devices button
        refresh_usb_btn = QPushButton("🔄 Refresh")
        refresh_usb_btn.setToolTip("Refresh the list of USB devices")
        refresh_usb_btn.clicked.connect(self.refresh_disk_info)
        device_layout.addWidget(refresh_usb_btn)
        
        usb_layout.addLayout(device_layout)
        
        # USB device info display
        self.usb_device_info = QLabel("Select a USB drive to see information")
        self.usb_device_info.setWordWrap(True)
        self.usb_device_info.setStyleSheet("padding: 10px; background-color: #f8f9fa; border-radius: 4px; margin: 5px 0;")
        usb_layout.addWidget(self.usb_device_info)
        
        # Step 3: Method selection
        step3_label = QLabel("Step 3: Select Creation Method")
        step3_label.setStyleSheet("font-weight: bold; color: #0078d4; margin-top: 10px;")
        usb_layout.addWidget(step3_label)
        
        method_layout = QVBoxLayout()
        
        # Method selection with descriptions
        method_layout_combo = QHBoxLayout()
        method_layout_combo.addWidget(QLabel("Method:"))
        self.method_combo = QComboBox()
        self.method_combo.addItems(["auto", "dd", "iso9660", "hybrid", "windows"])
        method_layout_combo.addWidget(self.method_combo)
        method_layout_combo.addStretch()
        method_layout.addLayout(method_layout_combo)
        
        # Description of methods
        self.method_description = QLabel(
            "<b>auto</b> - Automatically detect the best method based on the ISO file\n"
            "<b>dd</b> - Direct copy method, works with most Linux distributions\n"
            "<b>iso9660</b> - ISO filesystem method, preserves ability to add files\n" 
            "<b>hybrid</b> - Combination method for hybrid ISO images\n"
            "<b>windows</b> - Method optimized for Windows-based tools"
        )
        self.method_description.setStyleSheet("color: #555; padding: 5px; background-color: #f5f5f5; border-radius: 4px;")
        self.method_description.setWordWrap(True)
        method_layout.addWidget(self.method_description)
        usb_layout.addLayout(method_layout)
        
        # Step 4: Safety confirmation
        step4_label = QLabel("Step 4: Confirmation")
        step4_label.setStyleSheet("font-weight: bold; color: #0078d4; margin-top: 10px;")
        usb_layout.addWidget(step4_label)
        
        # Safety warning and confirmation
        safety_frame = QFrame()
        safety_frame.setStyleSheet("background-color: #fff3cd; padding: 10px; border-radius: 5px; margin: 5px 0;")
        safety_layout = QVBoxLayout(safety_frame)
        
        warning_label = QLabel("⚠️ <b>Warning:</b> This process will erase ALL DATA on the selected USB drive!")
        warning_label.setStyleSheet("color: #856404; font-weight: bold;")
        safety_layout.addWidget(warning_label)
        
        self.usb_confirm_checkbox = QCheckBox("I understand this will erase all data on the selected USB drive")
        safety_layout.addWidget(self.usb_confirm_checkbox)
        
        usb_layout.addWidget(safety_frame)
        
        # Create USB button
        self.create_usb_btn = QPushButton("🚀 Create Bootable USB")
        self.create_usb_btn.setObjectName("successButton")
        self.create_usb_btn.clicked.connect(self.usb_creator.create_bootable_usb)
        self.create_usb_btn.setEnabled(False)
        self.usb_confirm_checkbox.toggled.connect(self.update_usb_button_state)
        usb_layout.addWidget(self.create_usb_btn)
        
        layout.addWidget(usb_group)
        
        # Progress group with improved styling
        progress_group = QGroupBox("Creation Progress")
        progress_group.setStyleSheet("QGroupBox { padding-top: 15px; }")
        progress_layout = QVBoxLayout(progress_group)
        
        self.usb_progress = QProgressBar()
        self.usb_progress.setStyleSheet("""
            QProgressBar {
                text-align: center;
                border: 1px solid #bbb;
                border-radius: 4px;
                background-color: #f0f0f0;
                height: 24px;
            }
            QProgressBar::chunk {
                background-color: #2980b9;
                border-radius: 2px;
            }
        """)
        progress_layout.addWidget(self.usb_progress)
        
        self.usb_status_label = QLabel("Ready")
        self.usb_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.usb_status_label.setStyleSheet("padding: 5px; font-weight: bold;")
        progress_layout.addWidget(self.usb_status_label)
        
        # Cancel button
        self.cancel_usb_btn = QPushButton("❌ Cancel")
        # self.cancel_usb_btn.clicked.connect(self.cancel_usb_creation)
        self.cancel_usb_btn.setEnabled(False)
        progress_layout.addWidget(self.cancel_usb_btn)
        
        layout.addWidget(progress_group)
        layout.addStretch()
        
        self.tab_widget.addTab(usb_tab, "💾 USB Creator")
    
    def update_usb_button_state(self):
        """Update USB creation button state with more checks"""
        has_iso = self.iso_path_label.text() != "No file selected"
        
        # Get the actual device path from the combo box data
        has_device = False
        device_index = self.usb_device_combo.currentIndex()
        if device_index >= 0:
            has_device = bool(self.usb_device_combo.currentData())
            
        confirmed = self.usb_confirm_checkbox.isChecked()
        not_running = self.operation_thread is None or not self.operation_thread.isRunning()
        
        self.create_usb_btn.setEnabled(has_iso and has_device and confirmed and not_running)
        
        # Update status message
        if not has_iso:
            self.usb_status_label.setText("Please select an ISO file")
        elif not has_device:
            self.usb_status_label.setText("Please select a USB drive")
        elif not confirmed:
            self.usb_status_label.setText("Please confirm the warning")
        elif not_running:
            self.usb_status_label.setText("Ready to create bootable USB")
        else:
            self.usb_status_label.setText("Operation in progress...")
    
    def browse_iso_file(self):
        """Browse for ISO file with enhanced UI"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Linux ISO File", "", "ISO Files (*.iso);;All Files (*)"
        )
        
        if file_path:
            self.iso_path_label.setText(file_path)
            self.update_iso_info(file_path)
            self.update_usb_button_state()
    
    def update_iso_info(self, iso_path):
        """Display information about the selected ISO file"""
        if not iso_path or not os.path.exists(iso_path):
            self.iso_info_label.setText("Invalid file path")
            return
            
        try:
            # Get basic file info
            file_size = os.path.getsize(iso_path)
            file_name = os.path.basename(iso_path)
            
            # Convert size to human-readable format
            if file_size < 1024 * 1024:
                size_str = f"{file_size / 1024:.1f} KB"
            elif file_size < 1024 * 1024 * 1024:
                size_str = f"{file_size / (1024 * 1024):.1f} MB"
            else:
                size_str = f"{file_size / (1024 * 1024 * 1024):.2f} GB"
                
            # Try to determine the distro from filename
            distro = "Linux distribution"
            for known_distro in ["ubuntu", "debian", "fedora", "mint", "arch", "centos", "manjaro", "kali", 
                                 "tails", "opensuse", "elementary", "zorin", "puppy", "lubuntu", "xubuntu"]:
                if known_distro in file_name.lower():
                    distro = known_distro.capitalize()
                    break
                    
            info_text = (
                f"File: {file_name}\n"
                f"Size: {size_str}\n"
                f"Type: {distro} ISO image\n"
                f"Location: {os.path.dirname(iso_path)}"
            )
            
            # Check if file is actually an ISO
            if not file_name.lower().endswith('.iso'):
                info_text += "\n⚠️ Warning: File does not have .iso extension"
                
            self.iso_info_label.setText(info_text)
        except Exception as e:
            self.iso_info_label.setText(f"Error reading file: {str(e)}")
    
    def update_usb_device_info(self):
        """Update the device information display in the USB tab"""
        # Get the actual device path from the combo box data
        device_index = self.usb_device_combo.currentIndex()
        if device_index < 0:
            self.usb_device_info.setText("Please select a USB drive")
            return
            
        device = self.usb_device_combo.currentData()
        if not device:
            self.usb_device_info.setText("No USB drive selected")
            return
            
        # Get information about the device
        disks = self.disk_manager.list_physical_disks()
        
        # Find the device in our list
        selected_device = None
        for disk in disks:
            if disk['device'] == device:
                selected_device = disk
                break
                
        if not selected_device:
            self.usb_device_info.setText(f"Device: {device}")
            return
            
        # Check if it's a removable device
        is_removable = selected_device.get('removable', False)
        
        # Create the info text
        friendly_name = self.get_friendly_device_name(device, selected_device)
        info_text = f"<b>Device:</b> {device}"
        
        if friendly_name != device:
            info_text += f" ({friendly_name})"
            
        info_text += f"<br><b>Size:</b> {selected_device.get('size', 'Unknown')}"
        
        if selected_device.get('model'):
            info_text += f"<br><b>Model:</b> {selected_device['model']}"
            
        # Get partitions on this device
        partitions = self.disk_manager.list_partitions()
        device_partitions = [p for p in partitions if p['device'].startswith(device)]
        
        if device_partitions:
            info_text += "<br><b>Current Partitions:</b>"
            for part in device_partitions:
                part_text = f"<br>- {part['device']}"
                if part.get('type'):
                    part_text += f" ({part['type']})"
                if part.get('mountpoint'):
                    part_text += f" mounted at {part['mountpoint']}"
                info_text += part_text
                
        # Style based on removable status
        if is_removable:
            info_text += "<hr><p style='color: #2ecc71; font-weight: bold;'>✅ This is a removable device and suitable for creating a bootable USB.</p>"
            self.usb_device_info.setStyleSheet(
                "padding: 10px; background-color: #d4efdf; border: 1px solid #2ecc71; border-radius: 4px; margin: 5px 0;"
            )
        else:
            info_text += "<hr><p style='color: #e67e22; font-weight: bold;'>⚠️ This does not appear to be a removable device. Are you sure this is a USB drive?</p>"
            self.usb_device_info.setStyleSheet(
                "padding: 10px; background-color: #fef9e7; border: 1px solid #e67e22; border-radius: 4px; margin: 5px 0;"
            )
            
        # Check if the device is large enough
        iso_path = self.iso_path_label.text()
        if os.path.exists(iso_path):
            try:
                file_size = os.path.getsize(iso_path)
                # Parse device size string (like "16GB") to get value in bytes
                device_size_str = selected_device.get('size', '0')
                device_size_value = float(''.join(filter(str.isdigit, device_size_str)))
                device_size_unit = ''.join(filter(str.isalpha, device_size_str)).upper()
                
                device_size_bytes = device_size_value
                if 'KB' in device_size_unit:
                    device_size_bytes *= 1024
                elif 'MB' in device_size_unit:
                    device_size_bytes *= 1024 * 1024
                elif 'GB' in device_size_unit:
                    device_size_bytes *= 1024 * 1024 * 1024
                elif 'TB' in device_size_unit:
                    device_size_bytes *= 1024 * 1024 * 1024 * 1024
                
                if file_size > device_size_bytes:
                    info_text += "<p style='color: #e74c3c; font-weight: bold;'>⚠️ Warning: ISO file is larger than the USB drive capacity!</p>"
                    self.usb_device_info.setStyleSheet(
                        "padding: 10px; background-color: #fadbd8; border: 2px solid #e74c3c; border-radius: 4px; margin: 5px 0;"
                    )
            except Exception:
                # If we can't parse the size, just skip this check
                pass
            
        self.usb_device_info.setText(info_text)
        
    def refresh_disk_info(self):
        """Refresh disk and partition information with enhanced details"""
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
    
    def setup_refresh_timer(self):
        """Set up a timer for automatic refreshing of disk information"""
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_disk_info)
        # Default interval of 5 seconds as mentioned in the UI label
        self.refresh_timer.setInterval(5000)
        # Start the timer if auto-refresh checkbox exists and is checked
        # This is needed because the checkbox doesn't exist when this method is first called
        if hasattr(self, 'auto_refresh_checkbox') and self.auto_refresh_checkbox.isChecked():
            self.refresh_timer.start()
    
    def toggle_auto_refresh(self, enabled):
        """Toggle automatic refreshing of disk information based on checkbox state"""
        if enabled:
            # Start the timer if it exists
            if self.refresh_timer:
                self.refresh_timer.start()
                self.statusBar().showMessage("Auto-refresh enabled (every 5 seconds)")
        else:
            # Stop the timer if it exists
            if self.refresh_timer:
                self.refresh_timer.stop()
                self.statusBar().showMessage("Auto-refresh disabled")
    
    def update_disks_table(self, disks):
        """Update the physical disks table with enhanced information"""
        self.disks_table.setRowCount(len(disks))
        
        for row, disk in enumerate(disks):
            # Device path
            device_item = QTableWidgetItem(disk['device'])
            self.disks_table.setItem(row, 0, device_item)
            
            # Friendly name
            friendly_name = self.get_friendly_device_name(disk['device'], disk)
            self.disks_table.setItem(row, 1, QTableWidgetItem(friendly_name))
            
            # Size
            self.disks_table.setItem(row, 2, QTableWidgetItem(disk['size']))
            
            # Removable status with colorization
            is_removable = disk.get('removable', False)
            removable_item = QTableWidgetItem("Yes" if is_removable else "No")
            removable_item.setForeground(QColor("#2ecc71" if is_removable else "#7f8c8d"))
            if is_removable:
                removable_item.setFont(QFont("", -1, QFont.Weight.Bold))
            self.disks_table.setItem(row, 3, removable_item)
            
            # Model/Brand with better formatting
            model = disk.get('model', 'Unknown')
            if model and model.strip() and model != "Unknown":
                model_item = QTableWidgetItem(model)
            else:
                model_item = QTableWidgetItem("Not available")
                model_item.setForeground(QColor("#7f8c8d"))
            self.disks_table.setItem(row, 4, model_item)
            
            # Status (system drive, mounted, etc.)
            status = self.get_device_status(disk['device'])
            status_item = QTableWidgetItem(status)
            
            # Color the status based on type
            if "System" in status:
                status_item.setForeground(QColor("#e74c3c"))  # Red for system drives
                status_item.setFont(QFont("", -1, QFont.Weight.Bold))
            elif "Removable" in status:
                status_item.setForeground(QColor("#2ecc71"))  # Green for removable
            
            self.disks_table.setItem(row, 5, status_item)
            
            # If this is a system device, highlight the entire row for safety
            if not self.safety_manager.is_safe_device(disk['device']):
                for col in range(self.disks_table.columnCount()):
                    if col != 5:  # Skip the status column which already has custom color
                        self.disks_table.item(row, col).setBackground(QColor("#fadbd8"))  # Light red
        
        self.disks_table.resizeColumnsToContents()
        
    def show_disk_details(self):
        """Show detailed information about the selected disk"""
        selected_items = self.disks_table.selectedItems()
        if not selected_items:
            self.disk_details_text.setText("Select a device to see details.")
            return
            
        # Get the device path from the first column
        row = self.disks_table.row(selected_items[0])
        device_path = self.disks_table.item(row, 0).text()
        
        # Get all disks to find the selected one
        disks = self.disk_manager.list_physical_disks()
        selected_disk = None
        for disk in disks:
            if disk['device'] == device_path:
                selected_disk = disk
                break
                
        if not selected_disk:
            self.disk_details_text.setText("No detailed information available")
            return
            
        # Get safety information
        safety_info = self.safety_manager.get_device_info(device_path)
        
        # Format details nicely
        details = f"<b>Device:</b> {device_path}<br>"
        
        if selected_disk.get('model'):
            details += f"<b>Model:</b> {selected_disk['model']}<br>"
            
        details += f"<b>Size:</b> {selected_disk['size']}<br>"
        details += f"<b>Removable:</b> {'Yes' if selected_disk.get('removable', False) else 'No'}<br>"
        
        # Add warning for system devices
        if not self.safety_manager.is_safe_device(device_path):
            details += f"<p style='color: #e74c3c; font-weight: bold;'>⚠️ WARNING: This appears to be a system drive!</p>"
            
        # Show mounted partitions
        if safety_info.get('mounted_partitions'):
            details += "<b>Mounted Partitions:</b><br>"
            for part in safety_info['mounted_partitions']:
                details += f"- {part['device']} → {part['mountpoint']} ({part['fstype']})<br>"
        
        self.disk_details_text.setHtml(details)
        
    def update_partitions_table(self, partitions):
        """Update the partitions table with enhanced user-friendly information"""
        self.partitions_table.setRowCount(len(partitions))
        
        for row, part in enumerate(partitions):
            # Device path
            device_item = QTableWidgetItem(part['device'])
            self.partitions_table.setItem(row, 0, device_item)
            
            # Label/Name (mostly for Windows drives, but can have labels on Linux/Mac too)
            label = part.get('label', '')
            if not label:
                # Try to create a meaningful label
                mountpoint = part.get('mountpoint')
                if mountpoint:
                    if mountpoint == '/':
                        label = "System Root"
                    elif mountpoint == '/boot':
                        label = "Boot Partition"
                    elif mountpoint == '/home':
                        label = "User Files"
                    elif mountpoint.startswith('/media') or mountpoint.startswith('/mnt'):
                        label = "External Storage"
                    else:
                        # Use the last part of the path
                        label = os.path.basename(mountpoint)
                        
                # If that didn't work, use the device name
                if not label:
                    label = os.path.basename(part['device'])
            
            self.partitions_table.setItem(row, 1, QTableWidgetItem(label))
            
            # Size
            self.partitions_table.setItem(row, 2, QTableWidgetItem(part['size']))
            
            # Format filesystem type in a more user-friendly way
            fs_type = part.get('type', 'Unknown')
            if fs_type is None:
                fs_type = "Unknown"
            
            # Make filesystem types more user-friendly
            friendly_fs = fs_type
            if fs_type.lower() == 'ext4' or fs_type.lower() == 'ext3':
                friendly_fs = "Linux Filesystem"
            elif fs_type.lower() == 'ntfs':
                friendly_fs = "Windows Filesystem"
            elif fs_type.lower() == 'fat32' or fs_type.lower() == 'vfat':
                friendly_fs = "FAT32 (Compatible)"
            elif fs_type.lower() == 'exfat':
                friendly_fs = "exFAT (External)"
            elif fs_type.lower() == 'apfs':
                friendly_fs = "Apple Filesystem"
            elif fs_type.lower() == 'hfs+':
                friendly_fs = "Mac OS Extended"
                
            self.partitions_table.setItem(row, 3, QTableWidgetItem(friendly_fs))
            
            # Format mountpoint
            mountpoint = part.get('mountpoint', 'Not mounted')
            if mountpoint is None:
                mountpoint = "Not mounted"
                
            # Make mountpoints more user-friendly
            friendly_mount = mountpoint
            if mountpoint == '/':
                friendly_mount = "System Root Directory"
            elif mountpoint == '/boot':
                friendly_mount = "Boot Files"
            elif mountpoint == '/home':
                friendly_mount = "User Home Directories"
            elif mountpoint.startswith('/media') or mountpoint.startswith('/mnt'):
                # Extract the last part which is often the volume name
                mount_name = os.path.basename(mountpoint)
                if mount_name:
                    friendly_mount = f"Mounted as: {mount_name}"
                else:
                    friendly_mount = "External Media"
            
            self.partitions_table.setItem(row, 4, QTableWidgetItem(friendly_mount))
            
            # Usage with progress indication
            usage = "Unknown"
            if part.get('percent_used') is not None:
                percent_used = part['percent_used']
                usage = f"{percent_used:.1f}% used"
                
                # Add visual indicator of space usage
                if percent_used > 90:
                    usage = f"⚠️ {usage} (Almost Full)"
                elif percent_used > 75:
                    usage = f"⚠️ {usage} (Getting Full)"
                
                usage_item = QTableWidgetItem(usage)
                
                # Color code based on usage
                if percent_used > 90:
                    usage_item.setForeground(QColor("#e74c3c"))  # Red for almost full
                elif percent_used > 75:
                    usage_item.setForeground(QColor("#f39c12"))  # Orange for getting full
                elif percent_used < 25:
                    usage_item.setForeground(QColor("#2ecc71"))  # Green for lots of space
                
                self.partitions_table.setItem(row, 5, usage_item)
            else:
                self.partitions_table.setItem(row, 5, QTableWidgetItem("Unknown"))
            
            # Highlight system partitions for safety
            if mountpoint in ['/', '/boot', '/efi', '/bin', '/usr', '/etc', 'C:\\', 'C:\\Windows']:
                for col in range(self.partitions_table.columnCount()):
                    self.partitions_table.item(row, col).setBackground(QColor("#fadbd8"))  # Light red
                
        self.partitions_table.resizeColumnsToContents()
        
    def update_format_device_info(self):
        """Update the device information display in the format tab with enhanced user-friendly details"""
        # Get the actual device path from the combo box data
        device_index = self.format_device_combo.currentIndex()
        if device_index < 0:
            self.format_device_info.setText("Please select a device")
            self.format_device_info.setStyleSheet("padding: 10px; background-color: #f8f9fa; border-radius: 4px; margin: 5px 0;")
            return
            
        device = self.format_device_combo.itemData(device_index)
        if not device:
            self.format_device_info.setText("Please select a device")
            self.format_device_info.setStyleSheet("padding: 10px; background-color: #f8f9fa; border-radius: 4px; margin: 5px 0;")
            return
            
        # Get information about the device
        disks = self.disk_manager.list_physical_disks()
        partitions = self.disk_manager.list_partitions()
        
        # Find the device in our list
        selected_device = None
        
        for disk in disks:
            if disk['device'] == device:
                selected_device = disk
                break
                
        if not selected_device:
            for part in partitions:
                if part['device'] == device:
                    selected_device = part
                    break
        
        if not selected_device:
            self.format_device_info.setText("No information available for this device.")
            self.format_device_info.setStyleSheet("padding: 10px; background-color: #f8f9fa; border-radius: 4px; margin: 5px 0;")
            return
            
        # Check if this is a system drive
        is_system_drive = not self.safety_manager.is_safe_device(device)
        is_removable = selected_device.get('removable', False)
        
        # Get a friendly name for the device
        friendly_name = self.get_friendly_device_name(device, selected_device)
        
        # Format information with HTML for better formatting
        info = f"<div style='line-height: 1.5;'>"
        
        # Show user-friendly name prominently
        info += f"<h3 style='margin: 0 0 10px 0;'>{friendly_name}</h3>"
        
        # Technical details in a table format
        info += "<table style='width: 100%; border-collapse: collapse; margin-bottom: 10px;'>"
        info += f"<tr><td style='padding: 4px; font-weight: bold; width: 35%;'>Device Path:</td><td>{device}</td></tr>"
        if selected_device.get('model'):
            info += f"<tr><td style='padding: 4px; font-weight: bold;'>Model:</td><td>{selected_device['model']}</td></tr>"
        info += f"<tr><td style='padding: 4px; font-weight: bold;'>Size:</td><td>{selected_device['size']}</td></tr>"
        info += f"<tr><td style='padding: 4px; font-weight: bold;'>Removable Device:</td><td>{'Yes' if is_removable else 'No'}</td></tr>"
        info += f"<tr><td style='padding: 4px; font-weight: bold;'>Status:</td><td>{self.get_device_status(device)}</td></tr>"
        info += "</table>"
        
        # Add partition information in a more readable format
        device_partitions = [p for p in partitions if p['device'].startswith(device)]
        if device_partitions:
            info += f"<h4 style='margin: 5px 0;'>Current Partitions: {len(device_partitions)}</h4>"
            info += "<ul style='margin: 5px 0 10px 0; padding-left: 20px;'>"
            for part in device_partitions:
                part_info = f"{part['device']} ({part.get('type', 'Unknown')}) {part['size']}"
                if part.get('mountpoint'):
                    part_info += f" mounted at <b>{part['mountpoint']}</b>"
                info += f"<li>{part_info}</li>"
            info += "</ul>"
        
        # Add warning for system drives with more prominent styling
        if is_system_drive:
            info += "<div style='background-color: #ffebeb; border: 2px solid #e74c3c; border-radius: 4px; padding: 10px; margin-top: 10px;'>"
            info += "<span style='font-weight: bold; color: #e74c3c; font-size: 16px;'>⚠️ WARNING: System Drive Detected!</span><br>"
            info += "This appears to be a system drive containing important operating system files. "
            info += "Formatting this drive may damage your operating system and make your computer unbootable."
            info += "</div>"
            self.format_device_info.setStyleSheet("padding: 10px; background-color: #fff8f8; border: 1px solid #e0c0c0; border-radius: 4px; margin: 5px 0;")
        elif is_removable:
            info += "<div style='background-color: #ebfff0; border: 2px solid #2ecc71; border-radius: 4px; padding: 10px; margin-top: 10px;'>"
            info += "<span style='font-weight: bold; color: #27ae60; font-size: 16px;'>✅ Removable Device</span><br>"
            info += "This is a removable device that should be safe to format. Still, make sure you've backed up any important data."
            info += "</div>"
            self.format_device_info.setStyleSheet("padding: 10px; background-color: #f8fff8; border: 1px solid #c0e0c0; border-radius: 4px; margin: 5px 0;")
        else:
            info += "<div style='background-color: #fff8eb; border: 2px solid #f39c12; border-radius: 4px; padding: 10px; margin-top: 10px;'>"
            info += "<span style='font-weight: bold; color: #e67e22; font-size: 16px;'>⚠️ Storage Device</span><br>"
            info += "This is a non-removable storage device. Please verify that it doesn't contain important data before formatting."
            info += "</div>"
            self.format_device_info.setStyleSheet("padding: 10px; background-color: #fffcf5; border: 1px solid #e0d8c0; border-radius: 4px; margin: 5px 0;")
            
        info += "</div>"
        self.format_device_info.setHtml(info)
        
    def update_device_combos(self, disks):
        """Update device combo boxes with more descriptive names"""
        # Save current selections
        current_format_device = self.format_device_combo.currentText()
        current_usb_device = self.usb_device_combo.currentText()
        
        # Clear and repopulate
        self.format_device_combo.clear()
        self.usb_device_combo.clear()
        
        # Add all devices to format combo with descriptive names
        for disk in disks:
            friendly_name = self.get_friendly_device_name(disk['device'], disk)
            display_text = f"{disk['device']} - {friendly_name} ({disk['size']})"
            
            # Add warning indicator for system drives
            if not self.safety_manager.is_safe_device(disk['device']):
                display_text += " ⚠️ SYSTEM"
                
            # Add removable indicator
            if disk.get('removable', False):
                display_text += " ✓ REMOVABLE"
                
            self.format_device_combo.addItem(display_text, disk['device'])
            
            # Only add removable devices to USB combo
            if disk.get('removable', False):
                self.usb_device_combo.addItem(display_text, disk['device'])
                
        # Add partitions to format combo
        partitions = self.disk_manager.list_partitions()
        for part in partitions:
            # Create descriptive text
            desc = f"{part['device']} - {part['size']}"
            
            # Add filesystem type if available
            if part.get('type'):
                desc += f" ({part['type']})"
                
            # Add mountpoint if available
            if part.get('mountpoint'):
                mountpoint = part['mountpoint']
                if mountpoint in ['/', '/boot', '/efi']:
                    desc += f" ⚠️ {mountpoint} (SYSTEM)"
                else:
                    desc += f" @ {mountpoint}"
            
            self.format_device_combo.addItem(desc, part['device'])
        
        # Restore selections if still valid - need to search by stored data
        for i in range(self.format_device_combo.count()):
            if self.format_device_combo.itemData(i) == current_format_device:
                self.format_device_combo.setCurrentIndex(i)
                break
                
        for i in range(self.usb_device_combo.count()):
            if self.usb_device_combo.itemData(i) == current_usb_device:
                self.usb_device_combo.setCurrentIndex(i)
                break
                
        # Update the format device info
        self.update_format_device_info()
        
    def create_system_info_tab(self):
        """Create the system information tab with enhanced visual design"""
        info_tab = QWidget()
        layout = QVBoxLayout(info_tab)
        
        # Application info section
        app_group = QGroupBox("DiskForge Information")
        app_group.setStyleSheet("QGroupBox { background-color: #e1f5fe; border-radius: 8px; }")
        app_layout = QVBoxLayout(app_group)
        
        # Logo/Title area
        title_layout = QHBoxLayout()
        
        logo_label = QLabel("🔧")
        logo_label.setStyleSheet("font-size: 48px; padding: 10px;")
        title_layout.addWidget(logo_label)
        
        title_text = QLabel("<h2>DiskForge</h2><p>Cross-platform disk management tool</p>")
        title_layout.addWidget(title_text)
        title_layout.addStretch()
        
        # Version info
        version_label = QLabel("<b>Version:</b> 0.1.0")
        version_label.setStyleSheet("color: #666; padding: 5px;")
        title_layout.addWidget(version_label)
        
        app_layout.addLayout(title_layout)
        
        # Description
        description = QLabel(
            "DiskForge is a powerful disk management utility that helps you format drives and "
            "create bootable Linux USB drives. It works across Linux, macOS, and Windows platforms "
            "with both graphical and command-line interfaces."
        )
        description.setWordWrap(True)
        description.setStyleSheet("padding: 10px; color: #333;")
        app_layout.addWidget(description)
        
        # Features list
        features_text = """
        <b>Key Features:</b>
        <ul>
          <li>Cross-platform support for Linux, macOS, and Windows</li>
          <li>Format drives with various filesystems (ext4, FAT32, NTFS, exFAT)</li>
          <li>Create bootable Linux USB drives from ISO images</li>
          <li>Built-in safety features to prevent accidental data loss</li>
          <li>Real-time progress tracking with cancellation support</li>
          <li>Both graphical and command-line interfaces</li>
        </ul>
        """
        features_label = QLabel(features_text)
        features_label.setWordWrap(True)
        features_label.setStyleSheet("padding-left: 10px;")
        app_layout.addWidget(features_label)
        
        layout.addWidget(app_group)
        
        # System information section
        sys_group = QGroupBox("System Information")
        sys_group.setStyleSheet("QGroupBox { background-color: #f5f5f5; border-radius: 8px; }")
        sys_layout = QVBoxLayout(sys_group)
        
        # System info text area with improved formatting
        self.system_info_text = QTextEdit()
        self.system_info_text.setReadOnly(True)
        self.system_info_text.setFont(QFont("Consolas", 10))
        self.system_info_text.setStyleSheet("""
            QTextEdit {
                background-color: #ffffff;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 10px;
            }
        """)
        sys_layout.addWidget(self.system_info_text)
        
        # Refresh button
        refresh_info_btn = QPushButton("🔄 Refresh System Info")
        refresh_info_btn.clicked.connect(self.refresh_system_info)
        sys_layout.addWidget(refresh_info_btn)
        
        layout.addWidget(sys_group)
        
        self.tab_widget.addTab(info_tab, "ℹ️ System Info")
    
    def refresh_system_info(self):
        """Refresh system information with enhanced details and formatting"""
        import platform
        import psutil
        
        try:
            # System section
            system_info = f"""<h3>🖥️ System Information</h3>
<table width="100%" cellpadding="5" style="border-collapse: collapse;">
    <tr style="background-color: #f0f7ff;">
        <td width="40%"><b>Operating System:</b></td>
        <td>{platform.system()} {platform.release()}</td>
    </tr>
    <tr>
        <td><b>Platform:</b></td>
        <td>{platform.platform()}</td>
    </tr>
    <tr style="background-color: #f0f7ff;">
        <td><b>Architecture:</b></td>
        <td>{platform.machine()}</td>
    </tr>
    <tr>
        <td><b>Processor:</b></td>
        <td>{platform.processor() or "Unknown"}</td>
    </tr>
</table>"""

            # Hardware resources
            try:
                mem = psutil.virtual_memory()
                mem_total = self.format_bytes(mem.total)
                mem_used = self.format_bytes(mem.used)
                mem_percent = mem.percent
                
                disk = psutil.disk_usage('/')
                disk_total = self.format_bytes(disk.total)
                disk_used = self.format_bytes(disk.used)
                disk_percent = disk.percent
                
                hw_info = f"""<h3>💽 Hardware Resources</h3>
<table width="100%" cellpadding="5" style="border-collapse: collapse;">
    <tr style="background-color: #f0f7ff;">
        <td width="40%"><b>Memory (RAM):</b></td>
        <td>{mem_used} used of {mem_total} ({mem_percent}%)</td>
    </tr>
    <tr>
        <td><b>Disk Space (System):</b></td>
        <td>{disk_used} used of {disk_total} ({disk_percent}%)</td>
    </tr>
</table>"""
            except Exception as e:
                hw_info = f"<h3>💽 Hardware Resources</h3>\n<p>Unable to retrieve hardware info: {str(e)}</p>"
            
            # Python information
            py_info = f"""<h3>🐍 Python Information</h3>
<table width="100%" cellpadding="5" style="border-collapse: collapse;">
    <tr style="background-color: #f0f7ff;">
        <td width="40%"><b>Python Version:</b></td>
        <td>{platform.python_version()}</td>
    </tr>
    <tr>
        <td><b>Implementation:</b></td>
        <td>{platform.python_implementation()}</td>
    </tr>
</table>"""
            
            # DiskForge information
            app_info = f"""<h3>🔧 DiskForge Information</h3>
<table width="100%" cellpadding="5" style="border-collapse: collapse;">
    <tr style="background-color: #f0f7ff;">
        <td width="40%"><b>Version:</b></td>
        <td>0.1.0</td>
    </tr>
    <tr>
        <td><b>Path:</b></td>
        <td>{os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))}</td>
    </tr>
    <tr style="background-color: #f0f7ff;">
        <td><b>Mode:</b></td>
        <td>GUI (Graphical User Interface)</td>
    </tr>
    <tr>
        <td><b>Running as Administrator:</b></td>
        <td>{"Yes" if self.check_admin_privileges() else "No ⚠️ (some features may not work)"}</td>
    </tr>
</table>

<h3>🔍 Supported Operations</h3>
<ul>
    <li>List and examine physical disk devices</li>
    <li>Format drives with various filesystems</li>
    <li>Create bootable Linux USB drives from ISO files</li>
    <li>Monitor disk usage and information</li>
</ul>
"""
            
            # Combine all sections
            self.system_info_text.setHtml(f"{system_info}<br>{hw_info}<br>{py_info}<br>{app_info}")
            
        except Exception as e:
            self.system_info_text.setPlainText(f"Error retrieving system information: {str(e)}")
            
    def format_bytes(self, bytes_value):
        """Convert bytes to human-readable format"""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if bytes_value < 1024 or unit == "TB":
                return f"{bytes_value:.2f} {unit}"
            bytes_value /= 1024
            
    def check_admin_privileges(self):
        """Check if the application is running with admin/root privileges"""
        try:
            import platform
            if platform.system() == "Windows":
                try:
                    import ctypes
                    return ctypes.windll.shell32.IsUserAnAdmin() != 0
                except:
                    return False
            else:  # Linux/Mac
                return os.geteuid() == 0
        except:
            return False
    
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
    
    def format_device(self):
        """Format the selected device with improved user feedback"""
        # Get the actual device path from the combo box data
        device_index = self.format_device_combo.currentIndex()
        if device_index < 0:
            QMessageBox.warning(self, "Warning", "Please select a device to format.")
            return
            
        device = self.format_device_combo.itemData(device_index)
        filesystem = self.filesystem_combo.currentText()
        
        if not device:
            QMessageBox.warning(self, "Warning", "Please select a valid device to format.")
            return
            
        # Safety check
        if not self.safety_manager.is_safe_device(device):
            reply = QMessageBox.critical(
                self, "DANGEROUS OPERATION",
                f"<b>⚠️ WARNING: {device} appears to be a system device!</b><br><br>"
                f"Formatting this device could make your system <b>UNBOOTABLE</b>.<br><br>"
                f"This is <b>EXTREMELY DANGEROUS</b> and not recommended.<br><br>"
                "Are you absolutely sure you want to continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
                
        # Final confirmation with customized message based on device type
        device_info = self.safety_manager.get_device_info(device)
        
        confirmation_title = "Confirm Format"
        confirmation_icon = QMessageBox.Icon.Warning
        
        if device_info.get('is_removable', False):
            confirmation_message = (
                f"Are you sure you want to format {device} with {filesystem}?\n\n"
                f"This is a removable device and will be formatted with {filesystem}.\n"
                "All data on the device will be permanently deleted."
            )
        else:
            confirmation_title = "WARNING: Format Non-Removable Device"
            confirmation_message = (
                f"⚠️ You are about to format {device} with {filesystem}.\n\n"
                f"This appears to be a <b>non-removable device</b>.\n\n"
                f"Formatting will <b>PERMANENTLY DELETE ALL DATA</b> on the device!\n"
                f"This operation cannot be undone."
            )
            confirmation_icon = QMessageBox.Icon.Critical
        
        reply = QMessageBox.question(
            self, confirmation_title,
            confirmation_message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.start_format_operation(device, filesystem)
    
    def setup_custom_device_view(self):
        """Setup custom item delegates for device combo boxes to show color indicators"""
        device_delegate = self.DeviceItemDelegate(self, self.safety_manager)
        self.format_device_combo.setItemDelegate(device_delegate)
        self.usb_device_combo.setItemDelegate(device_delegate)


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