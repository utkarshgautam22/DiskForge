#!/usr/bin/env python3
"""
Setup script for DiskForge - Cross-platform disk management tool
"""

from setuptools import setup, find_packages
import platform
import os

# Read the README file
def read_readme():
    try:
        with open("README.md", "r", encoding="utf-8") as fh:
            return fh.read()
    except FileNotFoundError:
        return "DiskForge - Cross-platform disk management tool"

# Platform-specific dependencies
def get_platform_requirements():
    requirements = [
        "psutil>=5.9.0",
        "click>=8.0.0",
        "colorama>=0.4.0",
    ]
    
    # GUI dependencies (optional)
    gui_requirements = [
        "PyQt6>=6.4.0",
    ]
    
    # Platform-specific dependencies
    if platform.system() == "Linux":
        requirements.append("pyudev>=0.24.0")
    elif platform.system() == "Darwin":
        requirements.append("pyobjc>=7.3")
    elif platform.system() == "Windows":
        requirements.extend([
            "pywin32>=300",
            "wmi>=1.5.1"
        ])
    
    return requirements, gui_requirements

base_requirements, gui_requirements = get_platform_requirements()

setup(
    name="diskforge",
    version="0.1.0",
    author="DiskForge Team",
    author_email="",
    description="Cross-platform disk management tool for formatting drives and creating bootable USB drives",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/diskforge",
    project_urls={
        "Bug Tracker": "https://github.com/yourusername/diskforge/issues",
        "Documentation": "https://github.com/yourusername/diskforge/wiki",
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: System Administrators",
        "Intended Audience :: End Users/Desktop",
        "Topic :: System :: Systems Administration",
        "Topic :: Utilities",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
        "Environment :: Console",
        "Environment :: X11 Applications :: Qt",
    ],
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=base_requirements,
    extras_require={
        "gui": gui_requirements,
        "dev": [
            "pytest>=6.0",
            "black>=22.0",
            "flake8>=4.0",
            "mypy>=0.900",
        ],
        "all": gui_requirements + [
            "pytest>=6.0",
            "black>=22.0", 
            "flake8>=4.0",
            "mypy>=0.900",
        ]
    },
    entry_points={
        "console_scripts": [
            "diskforge=src.main:main",
            "diskforge-cli=src.cli.commands:cli",
            "diskforge-gui=src.gui.main_window:run_gui",
        ],
    },
    package_data={
        "src": ["assets/*"],
    },
    include_package_data=True,
    zip_safe=False,
    keywords="disk management, usb creator, bootable usb, format drive, cross-platform",
    platforms=["Linux", "Windows", "macOS"],
)