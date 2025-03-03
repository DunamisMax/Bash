#!/usr/bin/env python3
"""
Universal Downloader
--------------------------------------------------

A powerful and beautiful terminal-based utility for downloading files and media
with real-time progress tracking, Nord-themed UI, and intelligent handling of
various content types.

Features:
  • Supports downloading files via wget or curl
  • Downloads YouTube videos/playlists via yt-dlp with browser cookies
  • Real-time progress tracking with ETA and speed metrics
  • Cross-platform support (Windows, macOS, Linux)
  • Automatic dependency detection and installation
  • Beautiful Nord-themed terminal interface
  • Interactive and command-line modes

Usage:
  Run without arguments for interactive menu
  Or specify command: ./universal_downloader.py file <url> [options]
  Or for YouTube: ./universal_downloader.py youtube <url> [options]

  Options:
    -o, --output-dir <dir>   Set download directory
    -v, --verbose            Enable verbose output
    -h, --help               Show help information

Version: 4.0.0
"""

import argparse
import atexit
import datetime
import json
import os
import platform
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Callable, Union, Set


# ----------------------------------------------------------------
# Dependency Check and Imports
# ----------------------------------------------------------------
def install_missing_packages():
    """Install required Python packages if they're missing."""
    required_packages = ["rich", "pyfiglet", "requests"]
    missing_packages = []

    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)

    if missing_packages:
        print(f"Installing missing packages: {', '.join(missing_packages)}")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install"] + missing_packages,
                check=True,
                capture_output=True,
            )
            print("Successfully installed required packages. Restarting script...")
            # Restart the script to ensure imports work
            os.execv(sys.executable, [sys.executable] + sys.argv)
        except Exception as e:
            print(f"Failed to install required packages: {e}")
            print(
                "Please install them manually: pip install "
                + " ".join(missing_packages)
            )
            sys.exit(1)


# Try installing missing packages
install_missing_packages()

# Now import the installed packages
try:
    import requests
    import pyfiglet
    from rich.console import Console
    from rich.text import Text
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import (
        Progress,
        SpinnerColumn,
        TextColumn,
        BarColumn,
        TimeRemainingColumn,
        TaskProgressColumn,
        DownloadColumn,
    )
    from rich.align import Align
    from rich.style import Style
    from rich.prompt import Prompt, Confirm, IntPrompt
    from rich.live import Live
    from rich.columns import Columns
    from rich.rule import Rule
    from rich.traceback import install as install_rich_traceback
    from rich.highlighter import RegexHighlighter
    from rich.theme import Theme
except ImportError as e:
    print(f"Error importing required libraries: {e}")
    print("Please install them manually: pip install rich pyfiglet requests")
    sys.exit(1)

# Install rich traceback handler for better error reporting
install_rich_traceback(show_locals=True)


# ----------------------------------------------------------------
# Configuration & Constants
# ----------------------------------------------------------------
class AppConfig:
    """Application configuration settings."""

    VERSION = "4.0.0"
    APP_NAME = "Universal Downloader"
    APP_SUBTITLE = "Cross-Platform Download Tool"

    # Identify OS and set platform-specific settings
    PLATFORM = platform.system().lower()
    IS_WINDOWS = PLATFORM == "windows"
    IS_MACOS = PLATFORM == "darwin"
    IS_LINUX = PLATFORM == "linux"

    # Default download locations based on platform
    if IS_WINDOWS:
        DEFAULT_DOWNLOAD_DIR = os.path.join(os.path.expanduser("~"), "Downloads")
        TEMP_DIR = os.path.join(tempfile.gettempdir(), "universal_downloader")
        LOG_FILE = os.path.join(TEMP_DIR, "universal_downloader.log")
    elif IS_MACOS:
        DEFAULT_DOWNLOAD_DIR = os.path.join(os.path.expanduser("~"), "Downloads")
        TEMP_DIR = os.path.join(tempfile.gettempdir(), "universal_downloader")
        LOG_FILE = os.path.join(
            os.path.expanduser("~"), "Library", "Logs", "universal_downloader.log"
        )
    else:  # Linux and others
        DEFAULT_DOWNLOAD_DIR = os.path.join(os.path.expanduser("~"), "Downloads")
        TEMP_DIR = "/tmp/universal_downloader"
        LOG_FILE = (
            "/var/log/universal_downloader.log"
            if os.access("/var/log", os.W_OK)
            else os.path.join(os.path.expanduser("~"), ".universal_downloader.log")
        )

    # Host info
    try:
        HOSTNAME = socket.gethostname()
    except:
        HOSTNAME = "Unknown"

    # Progress display settings
    try:
        TERM_WIDTH = shutil.get_terminal_size().columns
    except:
        TERM_WIDTH = 80
    PROGRESS_WIDTH = min(50, TERM_WIDTH - 30)

    # Command timeouts
    DEFAULT_TIMEOUT = 300  # 5 minutes default timeout for commands
    DOWNLOAD_TIMEOUT = 7200  # 2 hours timeout for downloads

    # YouTube download settings
    YTDLP_OUTPUT_TEMPLATE = "%(title)s.%(ext)s"
    YTDLP_FORMAT_SELECTION = "best[ext=mp4]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best"

    # Browsers for cookie extraction, ordered by preference
    BROWSER_PRIORITIES = {
        "windows": ["chrome", "firefox", "edge", "brave", "opera"],
        "darwin": ["chrome", "firefox", "safari", "brave", "edge"],
        "linux": ["chrome", "firefox", "brave", "chromium", "edge"],
    }

    @classmethod
    def get_browser_list(cls) -> List[str]:
        """Get a list of browsers for the current platform, ordered by preference."""
        return cls.BROWSER_PRIORITIES.get(cls.PLATFORM, ["chrome", "firefox"])

    @classmethod
    def get_default_browser(cls) -> str:
        """Get the default browser for cookie extraction based on platform."""
        browsers = cls.get_browser_list()
        # Return the first one from the list
        return browsers[0] if browsers else "chrome"


# ----------------------------------------------------------------
# Nord-Themed Colors
# ----------------------------------------------------------------
class NordColors:
    """Nord color palette for consistent theming throughout the application."""

    # Polar Night (dark) shades
    POLAR_NIGHT_1 = "#2E3440"  # Darkest background shade
    POLAR_NIGHT_2 = "#3B4252"  # Dark background shade
    POLAR_NIGHT_3 = "#434C5E"  # Medium background shade
    POLAR_NIGHT_4 = "#4C566A"  # Light background shade

    # Snow Storm (light) shades
    SNOW_STORM_1 = "#D8DEE9"  # Darkest text color
    SNOW_STORM_2 = "#E5E9F0"  # Medium text color
    SNOW_STORM_3 = "#ECEFF4"  # Lightest text color

    # Frost (blues/cyans) shades
    FROST_1 = "#8FBCBB"  # Light cyan
    FROST_2 = "#88C0D0"  # Light blue
    FROST_3 = "#81A1C1"  # Medium blue
    FROST_4 = "#5E81AC"  # Dark blue

    # Aurora (accent) shades
    RED = "#BF616A"  # Red
    ORANGE = "#D08770"  # Orange
    YELLOW = "#EBCB8B"  # Yellow
    GREEN = "#A3BE8C"  # Green
    PURPLE = "#B48EAD"  # Purple


# Create a Rich Console with Nord theme
console = Console(
    theme=Theme(
        {
            "info": f"bold {NordColors.FROST_2}",
            "warning": f"bold {NordColors.YELLOW}",
            "error": f"bold {NordColors.RED}",
            "success": f"bold {NordColors.GREEN}",
            "url": f"underline {NordColors.FROST_3}",
            "filename": f"italic {NordColors.FROST_1}",
        }
    )
)


# ----------------------------------------------------------------
# Custom Exception Classes
# ----------------------------------------------------------------
class DownloaderError(Exception):
    """Base exception for Universal Downloader errors."""

    pass


class DependencyError(DownloaderError):
    """Raised when a required dependency is missing and cannot be installed."""

    pass


class DownloadError(DownloaderError):
    """Raised when a download fails."""

    pass


# ----------------------------------------------------------------
# Data Structures
# ----------------------------------------------------------------
class DownloadType(Enum):
    """Enum representing different types of downloads."""

    FILE = "file"
    YOUTUBE = "youtube"
    TORRENT = "torrent"  # Future expansion


@dataclass
class DownloadSource:
    """
    Represents a source to download from.

    Attributes:
        url: The URL to download from
        download_type: The type of download (file, YouTube, etc.)
        name: A friendly name for display (filename or title)
        size: Size in bytes if known, otherwise 0
        is_video: Whether this is a video source
        is_playlist: Whether this is a playlist
        metadata: Additional metadata about the source
    """

    url: str
    download_type: DownloadType = DownloadType.FILE
    name: str = ""
    size: int = 0
    is_video: bool = False
    is_playlist: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.name:
            self.name = self.get_filename_from_url()

    def get_filename_from_url(self) -> str:
        """Extract filename from URL, falling back to generic name if needed."""
        try:
            # Split on '?' to remove query parameters
            path = self.url.split("?")[0]
            # Get the last part of the path
            filename = os.path.basename(path)
            return filename if filename else "downloaded_file"
        except Exception:
            return "downloaded_file"


@dataclass
class DownloadStats:
    """
    Statistics about an ongoing or completed download.

    Attributes:
        bytes_downloaded: Number of bytes downloaded so far
        total_size: Total expected size in bytes
        start_time: When the download started
        end_time: When the download finished (or None if ongoing)
        rate_history: List of recent download rates for smoothing
    """

    bytes_downloaded: int = 0
    total_size: int = 0
    start_time: float = 0.0
    end_time: Optional[float] = None
    rate_history: List[float] = field(default_factory=list)

    def __post_init__(self):
        if self.start_time == 0.0:
            self.start_time = time.time()

    @property
    def is_complete(self) -> bool:
        """Return True if the download is complete."""
        return self.end_time is not None or (
            self.total_size > 0 and self.bytes_downloaded >= self.total_size
        )

    @property
    def progress_percentage(self) -> float:
        """Return the download progress as a percentage."""
        if self.total_size <= 0:
            return 0.0
        return min(100.0, (self.bytes_downloaded / self.total_size) * 100)

    @property
    def elapsed_time(self) -> float:
        """Return the elapsed time in seconds."""
        if self.end_time:
            return self.end_time - self.start_time
        return time.time() - self.start_time

    @property
    def average_rate(self) -> float:
        """Return the average download rate in bytes per second."""
        if not self.rate_history:
            if self.elapsed_time > 0:
                return self.bytes_downloaded / self.elapsed_time
            return 0.0
        return sum(self.rate_history) / len(self.rate_history)

    @property
    def eta_seconds(self) -> float:
        """Return the estimated time remaining in seconds."""
        if self.is_complete or self.average_rate <= 0:
            return 0.0
        return (self.total_size - self.bytes_downloaded) / self.average_rate

    def update_progress(self, new_bytes: int) -> None:
        """Update download progress with newly downloaded bytes."""
        now = time.time()
        if self.bytes_downloaded > 0:
            # Calculate the download rate since the last update
            time_diff = now - (self.end_time or self.start_time)
            if time_diff > 0:
                rate = new_bytes / time_diff
                self.rate_history.append(rate)
                # Keep only the last 5 rate measurements for smoothing
                if len(self.rate_history) > 5:
                    self.rate_history.pop(0)

        self.bytes_downloaded += new_bytes
        self.end_time = now

        # If we've reached or exceeded the total, mark as complete
        if self.total_size > 0 and self.bytes_downloaded >= self.total_size:
            self.bytes_downloaded = self.total_size  # Cap at total


@dataclass
class Dependency:
    """
    Represents a system dependency required by the application.

    Attributes:
        name: The name of the dependency
        display_name: A user-friendly display name
        command: The command to check if installed
        install_commands: Platform-specific install commands
        installed: Whether the dependency is installed
    """

    name: str
    display_name: str
    command: str  # Command to check if installed
    install_commands: Dict[str, List[str]] = field(default_factory=dict)
    installed: bool = False

    def check_installed(self) -> bool:
        """Check if the dependency is installed."""
        self.installed = bool(shutil.which(self.command))
        return self.installed

    def get_install_command(self) -> List[str]:
        """Get the appropriate install command for the current platform."""
        platform_key = AppConfig.PLATFORM
        if platform_key in self.install_commands:
            return self.install_commands[platform_key]
        return []


# Dictionary of supported dependencies with platform-specific install commands
DEPENDENCY_DEFINITIONS = {
    "wget": Dependency(
        name="wget",
        display_name="wget",
        command="wget",
        install_commands={
            "windows": ["winget", "install", "GnuWin32.Wget"],
            "darwin": ["brew", "install", "wget"],
            "linux": ["apt-get", "install", "-y", "wget"],
        },
    ),
    "curl": Dependency(
        name="curl",
        display_name="curl",
        command="curl",
        install_commands={
            "windows": ["winget", "install", "cURL.cURL"],
            "darwin": ["brew", "install", "curl"],
            "linux": ["apt-get", "install", "-y", "curl"],
        },
    ),
    "yt-dlp": Dependency(
        name="yt-dlp",
        display_name="yt-dlp",
        command="yt-dlp",
        install_commands={
            "windows": ["pip", "install", "yt-dlp"],
            "darwin": ["brew", "install", "yt-dlp"],
            "linux": ["pip", "install", "yt-dlp"],
        },
    ),
    "ffmpeg": Dependency(
        name="ffmpeg",
        display_name="FFmpeg",
        command="ffmpeg",
        install_commands={
            "windows": ["winget", "install", "Gyan.FFmpeg"],
            "darwin": ["brew", "install", "ffmpeg"],
            "linux": ["apt-get", "install", "-y", "ffmpeg"],
        },
    ),
}

# Define dependency groups
DEPENDENCY_GROUPS = {
    "common": ["curl"],
    "file": ["curl", "wget"],
    "youtube": ["yt-dlp", "ffmpeg"],
}


# ----------------------------------------------------------------
# Console and Logging Helpers
# ----------------------------------------------------------------
def create_header() -> Panel:
    """
    Create a high-tech ASCII art header with impressive styling.

    Returns:
        Panel containing the styled header
    """
    # Use smaller, more compact but still tech-looking fonts
    compact_fonts = ["slant", "small", "standard", "digital", "big"]

    # Try each font until we find one that works well
    for font_name in compact_fonts:
        try:
            fig = pyfiglet.Figlet(font=font_name, width=60)  # Constrained width
            ascii_art = fig.renderText(AppConfig.APP_NAME)

            # If we got a reasonable result, use it
            if ascii_art and len(ascii_art.strip()) > 0:
                break
        except Exception:
            continue

    # Custom ASCII art fallback if all else fails
    if not ascii_art or len(ascii_art.strip()) == 0:
        ascii_art = """
             _                          _                
 _   _ _ __ (_)_   _____ _ __ ___  __ _| |               
| | | | '_ \| \ \ / / _ \ '__/ __|/ _` | |               
| |_| | | | | |\ V /  __/ |  \__ \ (_| | |               
 \__,_|_| |_|_| \_/ \___|_|_ |___/\__,_|_|   _           
  __| | _____      ___ __ | | ___   __ _  __| | ___ _ __ 
 / _` |/ _ \ \ /\ / / '_ \| |/ _ \ / _` |/ _` |/ _ \ '__|
| (_| | (_) \ V  V /| | | | | (_) | (_| | (_| |  __/ |   
 \__,_|\___/ \_/\_/ |_| |_|_|\___/ \__,_|\__,_|\___|_|   
        """

    # Clean up extra whitespace that might cause display issues
    ascii_lines = [line for line in ascii_art.split("\n") if line.strip()]

    # Create a high-tech gradient effect with Nord colors
    colors = [
        NordColors.FROST_1,
        NordColors.FROST_2,
        NordColors.FROST_3,
        NordColors.FROST_4,
    ]

    styled_text = ""
    for i, line in enumerate(ascii_lines):
        color = colors[i % len(colors)]
        styled_text += f"[bold {color}]{line}[/]\n"

    # Add decorative tech elements
    tech_border = f"[{NordColors.FROST_3}]" + "━" * 50 + "[/]"
    styled_text = tech_border + "\n" + styled_text + tech_border

    # Create a panel with sufficient padding to avoid cutoff
    header_panel = Panel(
        Text.from_markup(styled_text),
        border_style=Style(color=NordColors.FROST_1),
        padding=(1, 2),
        title=f"[bold {NordColors.SNOW_STORM_2}]v{AppConfig.VERSION}[/]",
        title_align="right",
        subtitle=f"[bold {NordColors.SNOW_STORM_1}]{AppConfig.APP_SUBTITLE}[/]",
        subtitle_align="center",
    )

    return header_panel


def print_message(
    text: str, style: str = NordColors.FROST_2, prefix: str = "•"
) -> None:
    """
    Print a styled message.

    Args:
        text: The message to display
        style: The color style to use
        prefix: The prefix symbol
    """
    console.print(f"[{style}]{prefix} {text}[/{style}]")


def print_step(message: str) -> None:
    """Print a step description."""
    print_message(message, NordColors.FROST_3, "➜")


def print_success(message: str) -> None:
    """Print a success message."""
    print_message(message, NordColors.GREEN, "✓")


def print_warning(message: str) -> None:
    """Print a warning message."""
    print_message(message, NordColors.YELLOW, "⚠")


def print_error(message: str) -> None:
    """Print an error message."""
    print_message(message, NordColors.RED, "✗")


def display_panel(
    message: str, style: str = NordColors.FROST_2, title: Optional[str] = None
) -> None:
    """
    Display a message in a styled panel.

    Args:
        message: The message to display
        style: The color style to use
        title: Optional panel title
    """
    panel = Panel(
        Text.from_markup(f"[bold {style}]{message}[/]"),
        border_style=Style(color=style),
        padding=(1, 2),
        title=f"[bold {style}]{title}[/]" if title else None,
    )
    console.print(panel)


def format_size(num_bytes: float) -> str:
    """Convert bytes to a human-readable string."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num_bytes < 1024:
            return f"{num_bytes:.2f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.2f} PB"


def format_time(seconds: float) -> str:
    """Format seconds into a human-readable time string."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds / 60:.1f}m"
    else:
        return f"{seconds / 3600:.1f}h"


def setup_logging(log_file: str = AppConfig.LOG_FILE) -> None:
    """Configure logging to file."""
    import logging

    try:
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        logging.basicConfig(
            filename=log_file,
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        print_step(f"Logging configured to: {log_file}")
    except Exception as e:
        print_warning(f"Could not set up logging to {log_file}: {e}")
        print_step("Continuing without file logging...")


# ----------------------------------------------------------------
# Command Execution Helper
# ----------------------------------------------------------------
def run_command(
    cmd: List[str],
    env: Optional[Dict[str, str]] = None,
    check: bool = True,
    capture_output: bool = True,
    timeout: int = AppConfig.DEFAULT_TIMEOUT,
    verbose: bool = False,
) -> subprocess.CompletedProcess:
    """
    Executes a system command and returns the CompletedProcess.

    Args:
        cmd: Command and arguments as a list
        env: Environment variables for the command
        check: Whether to check the return code
        capture_output: Whether to capture stdout/stderr
        timeout: Command timeout in seconds
        verbose: Whether to print detailed information

    Returns:
        CompletedProcess instance with command results
    """
    try:
        cmd_str = " ".join(cmd)
        if verbose:
            print_step(f"Executing: {cmd_str[:80]}{'...' if len(cmd_str) > 80 else ''}")

        # On Windows, handle command execution differently
        if AppConfig.IS_WINDOWS and cmd[0] not in ["pip", "python"]:
            # For Windows, ensure the command is executed in a shell
            result = subprocess.run(
                cmd,
                env=env or os.environ.copy(),
                check=check,
                text=True,
                capture_output=capture_output,
                timeout=timeout,
                shell=True,
            )
        else:
            result = subprocess.run(
                cmd,
                env=env or os.environ.copy(),
                check=check,
                text=True,
                capture_output=capture_output,
                timeout=timeout,
            )
        return result
    except subprocess.CalledProcessError as e:
        print_error(f"Command failed: {' '.join(cmd)}")
        if e.stdout and verbose:
            console.print(f"[dim]Stdout: {e.stdout.strip()}[/dim]")
        if e.stderr:
            console.print(f"[bold {NordColors.RED}]Stderr: {e.stderr.strip()}[/]")
        raise
    except subprocess.TimeoutExpired:
        print_error(f"Command timed out after {timeout} seconds")
        raise
    except Exception as e:
        print_error(f"Error executing command: {e}")
        raise


# ----------------------------------------------------------------
# Signal Handling and Cleanup
# ----------------------------------------------------------------
def cleanup() -> None:
    """Perform any cleanup tasks before exit."""
    print_message("Cleaning up...", NordColors.FROST_3)


def signal_handler(sig: int, frame: Any) -> None:
    """
    Handle process termination signals gracefully.

    Args:
        sig: Signal number
        frame: Current stack frame
    """
    sig_name = str(sig)
    if hasattr(signal, "Signals"):
        try:
            sig_name = signal.Signals(sig).name
        except ValueError:
            pass

    print_message(f"Process interrupted by signal {sig_name}", NordColors.YELLOW, "⚠")
    cleanup()
    sys.exit(128 + sig)


# Register signal handlers (if supported by platform)
try:
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
except (AttributeError, ValueError):
    # Some signals might not be available on all platforms
    pass
atexit.register(cleanup)


# ----------------------------------------------------------------
# System and Dependency Management
# ----------------------------------------------------------------
def is_admin_or_root() -> bool:
    """
    Check if the script is running with administrator/root privileges.

    Returns:
        True if running with elevated privileges, False otherwise
    """
    try:
        if AppConfig.IS_WINDOWS:
            import ctypes

            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        else:
            return os.geteuid() == 0
    except:
        return False


def check_dependencies(required_deps: List[str]) -> Dict[str, bool]:
    """
    Check if required dependencies are installed.

    Args:
        required_deps: List of dependency names to check

    Returns:
        Dictionary mapping dependency names to their installation status
    """
    results = {}
    for dep_name in required_deps:
        if dep_name in DEPENDENCY_DEFINITIONS:
            dep = DEPENDENCY_DEFINITIONS[dep_name]
            results[dep_name] = dep.check_installed()
        else:
            results[dep_name] = False
    return results


def install_dependency(dependency: Dependency, verbose: bool = False) -> bool:
    """
    Install a single dependency.

    Args:
        dependency: The Dependency object to install
        verbose: Whether to show verbose output

    Returns:
        True if installation succeeded, False otherwise
    """
    install_cmd = dependency.get_install_command()
    if not install_cmd:
        print_error(
            f"No installation method available for {dependency.display_name} on {AppConfig.PLATFORM}"
        )
        return False

    try:
        # For Windows, check if we need to use an alternative installation method
        if AppConfig.IS_WINDOWS:
            # If winget is not available, try alternative methods
            if install_cmd[0] == "winget" and not shutil.which("winget"):
                if dependency.name == "wget":
                    # Use pip for wget on Windows as alternative
                    install_cmd = ["pip", "install", "wget"]
                elif dependency.name == "curl":
                    # Curl is usually included in Windows 10+
                    print_warning(
                        "curl should be available on Windows 10+. If it's not working, please install it manually."
                    )
                    return False

        # For package managers that need sudo, prepend sudo if not root
        if (
            not is_admin_or_root()
            and AppConfig.IS_LINUX
            and install_cmd[0] in ["apt-get", "apt", "yum", "dnf"]
        ):
            install_cmd = ["sudo"] + install_cmd

        print_step(f"Installing {dependency.display_name}...")
        result = run_command(install_cmd, verbose=verbose, check=False)

        # Verify installation
        if dependency.check_installed():
            print_success(f"Successfully installed {dependency.display_name}")
            return True
        else:
            print_error(
                f"Installation command completed but {dependency.display_name} is still not available"
            )
            return False
    except Exception as e:
        print_error(f"Failed to install {dependency.display_name}: {e}")
        return False


def install_dependencies(deps: List[str], verbose: bool = False) -> bool:
    """
    Attempt to install missing dependencies using platform-specific methods.

    Args:
        deps: List of dependency names to install
        verbose: Whether to show verbose output

    Returns:
        True if all dependencies were installed successfully, False otherwise
    """
    print_step(f"Installing dependencies: {', '.join(deps)}")

    with Progress(
        SpinnerColumn("dots", style=f"bold {NordColors.FROST_1}"),
        TextColumn(f"[bold {NordColors.FROST_2}]Installing dependencies"),
        BarColumn(
            bar_width=40,
            style=NordColors.FROST_4,
            complete_style=NordColors.FROST_2,
        ),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        # Create a task for overall progress
        install_task = progress.add_task("Installing packages", total=len(deps))
        success_count = 0

        for dep_name in deps:
            if dep_name not in DEPENDENCY_DEFINITIONS:
                print_warning(f"Unknown dependency: {dep_name}")
                progress.advance(install_task)
                continue

            dep = DEPENDENCY_DEFINITIONS[dep_name]
            if dep.check_installed():
                print_success(f"{dep.display_name} is already installed")
                success_count += 1
                progress.advance(install_task)
                continue

            if install_dependency(dep, verbose):
                success_count += 1

            progress.advance(install_task)

    if success_count == len(deps):
        print_success(f"All dependencies installed successfully")
        return True
    else:
        print_warning(f"Installed {success_count}/{len(deps)} dependencies")
        return False


def check_internet_connectivity() -> bool:
    """
    Check for internet connectivity by attempting to connect to well-known hosts.

    Returns:
        True if internet is available, False otherwise
    """
    print_step("Checking internet connectivity...")
    test_urls = [
        "https://www.google.com",
        "https://www.cloudflare.com",
        "https://www.microsoft.com",
    ]

    for url in test_urls:
        try:
            response = requests.head(url, timeout=5)
            if response.status_code == 200:
                print_success(f"Internet connection available")
                return True
        except:
            continue

    print_warning(
        "No internet connection detected. Some features may not work properly."
    )
    return False


def ensure_directory(path: str) -> None:
    """
    Ensure that a directory exists, creating it if necessary.

    Args:
        path: Directory path to ensure exists
    """
    try:
        os.makedirs(path, exist_ok=True)
        print_step(f"Directory ensured: {path}")
    except Exception as e:
        print_error(f"Failed to create directory '{path}': {e}")
        sys.exit(1)


# ----------------------------------------------------------------
# Download Information Functions
# ----------------------------------------------------------------
def get_file_size(url: str) -> int:
    """
    Retrieve the file size in bytes using a HEAD request.

    Args:
        url: URL to check

    Returns:
        File size in bytes, or 0 if size cannot be determined
    """
    try:
        response = requests.head(url, timeout=10, allow_redirects=True)
        content_length = response.headers.get("content-length")
        if content_length and content_length.isdigit():
            return int(content_length)
        return 0
    except Exception as e:
        print_warning(f"Could not determine file size for {url}: {e}")
        return 0


def get_youtube_info(url: str, browser: str = None) -> Tuple[str, bool, int]:
    """
    Get basic info about a YouTube URL.

    Args:
        url: YouTube URL
        browser: Browser to use for cookie extraction (optional)

    Returns:
        Tuple of (title, is_playlist, estimated_size)
    """
    if not browser:
        browser = AppConfig.get_default_browser()

    title = "Unknown video"
    is_playlist = False
    estimated_size = 0

    if not check_dependencies(["yt-dlp"])["yt-dlp"]:
        print_warning("yt-dlp is not installed. Cannot get YouTube info.")
        return title, is_playlist, estimated_size

    try:
        # First check if it's a playlist
        cmd = [
            "yt-dlp",
            "--no-warnings",
            "--flat-playlist",
            "--print",
            "playlist_id",
            url,
        ]
        try:
            # Add cookies if we have the browser available
            if browser:
                cmd = ["yt-dlp", "--cookies-from-browser", browser] + cmd[1:]
        except:
            pass

        result = run_command(cmd, capture_output=True, check=False)
        is_playlist = bool(result.stdout.strip())

        # Get the title
        if is_playlist:
            cmd = [
                "yt-dlp",
                "--no-warnings",
                "--flat-playlist",
                "--print",
                "playlist_title",
                url,
            ]
            # Add cookies if available
            if browser:
                cmd[1:1] = ["--cookies-from-browser", browser]

            result = run_command(cmd, capture_output=True, check=False)
            if result.stdout.strip():
                title = result.stdout.strip()
        else:
            cmd = [
                "yt-dlp",
                "--no-warnings",
                "--print",
                "title",
                url,
            ]
            # Add cookies if available
            if browser:
                cmd[1:1] = ["--cookies-from-browser", browser]

            result = run_command(cmd, capture_output=True, check=False)
            if result.stdout.strip():
                title = result.stdout.strip()

            # Try to estimate size
            if not is_playlist:
                cmd = [
                    "yt-dlp",
                    "--no-warnings",
                    "--print",
                    "filesize",
                    url,
                ]
                if browser:
                    cmd[1:1] = ["--cookies-from-browser", browser]

                result = run_command(cmd, capture_output=True, check=False)
                if result.stdout.strip().isdigit():
                    estimated_size = int(result.stdout.strip())

                # If size estimation fails, try using duration
                if estimated_size == 0:
                    cmd = [
                        "yt-dlp",
                        "--no-warnings",
                        "--print",
                        "duration",
                        url,
                    ]
                    if browser:
                        cmd[1:1] = ["--cookies-from-browser", browser]

                    result = run_command(cmd, capture_output=True, check=False)
                    if (
                        result.stdout.strip()
                        and result.stdout.strip().replace(".", "", 1).isdigit()
                    ):
                        duration = float(result.stdout.strip())
                        # Rough estimate: ~10 MB per minute of video at high quality
                        estimated_size = int(duration * 60 * 10 * 1024)
    except Exception as e:
        print_warning(f"Could not get YouTube info: {e}")

    return title, is_playlist, estimated_size


# ----------------------------------------------------------------
# Download Functions
# ----------------------------------------------------------------
def download_file(url: str, output_dir: str, verbose: bool = False) -> bool:
    """
    Download a file using requests or curl/wget.

    Args:
        url: The URL to download from
        output_dir: Directory to save the file in
        verbose: Whether to show verbose output

    Returns:
        True if download was successful, False otherwise
    """
    try:
        # Create a DownloadSource object
        source = DownloadSource(url=url, download_type=DownloadType.FILE)
        source.size = get_file_size(url)
        filename = source.name

        # Make sure the URL is safely encoded
        safe_url = urllib.parse.quote(url, safe=":/?&=")

        # Ensure output directory exists
        ensure_directory(output_dir)
        output_path = os.path.join(output_dir, filename)

        print_step(f"Downloading: {url}")
        print_step(f"Destination: {output_path}")

        if source.size:
            print_step(f"File size: {format_size(source.size)}")
        else:
            print_warning("File size unknown; progress will be indeterminate")

        # Download stats to track progress
        stats = DownloadStats(total_size=source.size)

        # Determine if we should use Python's requests, curl, or wget
        use_requests = True
        if not source.size:
            # For unknown size, prefer curl or wget for better progress reporting
            if check_dependencies(["curl"])["curl"]:
                use_requests = False
                downloader = "curl"
            elif check_dependencies(["wget"])["wget"]:
                use_requests = False
                downloader = "wget"
            else:
                use_requests = True

        # Use Progress from rich for a nicer display
        if use_requests and source.size > 0:
            # Use requests with progress bar for known size
            with Progress(
                SpinnerColumn("dots", style=f"bold {NordColors.FROST_1}"),
                TextColumn(f"[bold {NordColors.FROST_2}]Downloading"),
                BarColumn(
                    bar_width=AppConfig.PROGRESS_WIDTH,
                    style=NordColors.FROST_4,
                    complete_style=NordColors.FROST_2,
                ),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                DownloadColumn(),
                TextColumn(f"[{NordColors.GREEN}]{{task.fields[rate]}}"),
                TimeRemainingColumn(),
                console=console,
            ) as progress:
                download_task = progress.add_task(
                    "Downloading",
                    total=source.size,
                    completed=0,
                    rate="0 KB/s",
                )

                # Stream the download with requests
                with requests.get(
                    safe_url, stream=True, timeout=AppConfig.DOWNLOAD_TIMEOUT
                ) as response:
                    response.raise_for_status()
                    with open(output_path, "wb") as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                # Update progress
                                stats.update_progress(len(chunk))
                                progress.update(
                                    download_task,
                                    completed=stats.bytes_downloaded,
                                    rate=f"{format_size(stats.average_rate)}/s",
                                )

        elif not use_requests:
            # Use curl or wget with their own progress reporting
            if downloader == "curl":
                cmd = [
                    "curl",
                    "--progress-bar",
                    "--location",  # Follow redirects
                    "--output",
                    output_path,
                    safe_url,
                ]
            else:  # wget
                cmd = [
                    "wget",
                    "--progress=bar:force",
                    "--output-document",
                    output_path,
                    safe_url,
                ]

            with Progress(
                SpinnerColumn("dots", style=f"bold {NordColors.FROST_1}"),
                TextColumn(f"[bold {NordColors.FROST_2}]Downloading {filename}"),
                TextColumn(f"[{NordColors.SNOW_STORM_1}]Time: {{task.elapsed:.1f}}s"),
                console=console,
            ) as progress:
                task = progress.add_task("Downloading")
                run_command(cmd, verbose=verbose)

        else:
            # Use requests for unknown size (no progress bar)
            with Progress(
                SpinnerColumn("dots", style=f"bold {NordColors.FROST_1}"),
                TextColumn(f"[bold {NordColors.FROST_2}]Downloading {filename}"),
                TextColumn(f"[{NordColors.SNOW_STORM_1}]Time: {{task.elapsed:.1f}}s"),
                console=console,
            ) as progress:
                task = progress.add_task("Downloading")
                response = requests.get(safe_url, timeout=AppConfig.DOWNLOAD_TIMEOUT)
                response.raise_for_status()
                with open(output_path, "wb") as f:
                    f.write(response.content)

        # Check if download was successful
        if not os.path.exists(output_path):
            print_error("Download failed: Output file not found")
            return False

        # Show final stats
        file_stats = os.stat(output_path)
        download_time = time.time() - stats.start_time
        download_speed = file_stats.st_size / max(download_time, 0.1)

        display_panel(
            f"Downloaded: {filename}\n"
            f"Size: {format_size(file_stats.st_size)}\n"
            f"Time: {format_time(download_time)}\n"
            f"Speed: {format_size(download_speed)}/s\n"
            f"Location: {output_path}",
            style=NordColors.GREEN,
            title="Download Complete",
        )
        return True
    except Exception as e:
        print_error(f"Download failed: {e}")
        return False


def download_youtube(
    url: str, output_dir: str, browser: str = None, verbose: bool = False
) -> bool:
    """
    Download a YouTube video using yt-dlp with browser cookies.

    Args:
        url: YouTube URL to download from
        output_dir: Directory to save the video in
        browser: Browser to use for cookie extraction (optional)
        verbose: Whether to show verbose output

    Returns:
        True if download was successful, False otherwise
    """
    if not browser:
        browser = AppConfig.get_default_browser()

    try:
        # Ensure output directory exists
        ensure_directory(output_dir)

        # Get YouTube video information
        title, is_playlist, estimated_size = get_youtube_info(url, browser)

        # Create DownloadSource
        source = DownloadSource(
            url=url,
            download_type=DownloadType.YOUTUBE,
            name=title,
            size=estimated_size,
            is_video=True,
            is_playlist=is_playlist,
        )

        # Show information panel
        content_type = "Playlist" if is_playlist else "Video"
        info_text = f"Title: {title}\nType: {content_type}\n"

        if not is_playlist and estimated_size:
            info_text += f"Estimated size: {format_size(estimated_size)}\n"

        info_text += f"Destination: {output_dir}"

        display_panel(info_text, style=NordColors.FROST_3, title="YouTube Download")

        # Prepare output template and full path
        output_template = os.path.join(output_dir, AppConfig.YTDLP_OUTPUT_TEMPLATE)

        # Prepare command with browser cookies and format selection
        cmd = [
            "yt-dlp",
            "--cookies-from-browser",
            browser,  # Use browser cookies
            "-S",
            AppConfig.YTDLP_FORMAT_SELECTION,  # Format selection
            "-o",
            output_template,  # Output template
        ]

        if verbose:
            cmd.append("--verbose")
        else:
            cmd.append("--progress")

        cmd.append(url)

        # For playlist or verbose mode, use simpler progress display
        if is_playlist or verbose:
            with Progress(
                SpinnerColumn("dots", style=f"bold {NordColors.FROST_1}"),
                TextColumn(f"[bold {NordColors.FROST_2}]Downloading {content_type}"),
                TextColumn(f"[{NordColors.SNOW_STORM_1}]Time: {{task.elapsed:.1f}}s"),
                console=console,
            ) as progress:
                task = progress.add_task("Downloading")
                run_command(cmd, verbose=verbose, timeout=AppConfig.DOWNLOAD_TIMEOUT)
        else:
            # For single videos, parse output for progress information
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )

            with Progress(
                SpinnerColumn("dots", style=f"bold {NordColors.FROST_1}"),
                TextColumn(f"[bold {NordColors.FROST_2}]Downloading"),
                BarColumn(
                    bar_width=AppConfig.PROGRESS_WIDTH,
                    style=NordColors.FROST_4,
                    complete_style=NordColors.FROST_2,
                ),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeRemainingColumn(),
                console=console,
            ) as progress:
                task = progress.add_task("Downloading Video", total=100)
                stage = "Preparing"

                # Parse yt-dlp output for progress
                while True:
                    line = process.stdout.readline()
                    if not line:
                        break

                    # Update progress based on output
                    if "[download]" in line and "%" in line:
                        try:
                            parts = line.split()
                            for part in parts:
                                if "%" in part:
                                    pct_str = part.rstrip("%").rstrip(",")
                                    progress.update(task, completed=float(pct_str))
                                    break
                        except Exception:
                            pass
                    elif "Downloading video" in line:
                        stage = "Downloading video"
                        progress.update(task, description=stage)
                    elif "Downloading audio" in line:
                        stage = "Downloading audio"
                        progress.update(task, description=stage)
                    elif "Merging formats" in line:
                        stage = "Merging formats"
                        progress.update(task, completed=99, description=stage)

                process.wait()
                if process.returncode != 0:
                    print_error("Download failed with non-zero exit code")
                    return False

        display_panel(
            f"Successfully downloaded: {title}\nLocation: {output_dir}",
            style=NordColors.GREEN,
            title="Download Complete",
        )
        return True
    except Exception as e:
        print_error(f"Download failed: {e}")
        return False


# ----------------------------------------------------------------
# Command Functions
# ----------------------------------------------------------------
def cmd_file_download(url: str, output_dir: str, verbose: bool) -> int:
    """
    Execute the file download command after ensuring dependencies.

    Args:
        url: URL to download
        output_dir: Directory to save to
        verbose: Whether to show verbose output

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    required = DEPENDENCY_GROUPS["file"]

    # Check dependencies
    dep_status = check_dependencies(required)
    missing_deps = [dep for dep, installed in dep_status.items() if not installed]

    if missing_deps:
        print_warning(f"Missing dependencies: {', '.join(missing_deps)}")

        if Confirm.ask("Would you like to install missing dependencies?", default=True):
            if not install_dependencies(missing_deps, verbose):
                print_error("Failed to install all required dependencies")
                return 1
        else:
            print_warning("Continuing with limited functionality...")

    # Execute download
    success = download_file(url, output_dir, verbose)
    return 0 if success else 1


def cmd_youtube_download(
    url: str, output_dir: str, browser: str = None, verbose: bool = False
) -> int:
    """
    Execute the YouTube download command after ensuring dependencies.

    Args:
        url: YouTube URL to download
        output_dir: Directory to save to
        browser: Browser to use for cookie extraction
        verbose: Whether to show verbose output

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    required = DEPENDENCY_GROUPS["youtube"]

    # Check dependencies
    dep_status = check_dependencies(required)
    missing_deps = [dep for dep, installed in dep_status.items() if not installed]

    if missing_deps:
        print_warning(f"Missing dependencies: {', '.join(missing_deps)}")

        if Confirm.ask("Would you like to install missing dependencies?", default=True):
            if not install_dependencies(missing_deps, verbose):
                print_error("Failed to install all required dependencies")
                return 1
        else:
            print_error("Cannot continue without required dependencies")
            return 1

    # Get browser for cookie extraction if not provided
    if not browser:
        available_browsers = []
        for browser_option in AppConfig.get_browser_list():
            browser_path = None
            if AppConfig.IS_LINUX:
                # Check if the browser exists in common Linux paths
                paths = [
                    f"/usr/bin/{browser_option}",
                    f"/usr/local/bin/{browser_option}",
                    f"/snap/bin/{browser_option}",
                ]
                for path in paths:
                    if os.path.exists(path):
                        browser_path = path
                        break
            else:
                # For Windows and macOS, use the browser name as yt-dlp will find it
                browser_path = browser_option

            if browser_path:
                available_browsers.append(browser_option)

        if available_browsers:
            if len(available_browsers) == 1:
                browser = available_browsers[0]
            else:
                console.print(
                    f"\n[bold {NordColors.FROST_2}]Select browser for cookie extraction:[/]"
                )
                for i, b in enumerate(available_browsers, 1):
                    console.print(f"  {i}. {b}")

                choice = IntPrompt.ask(
                    "Enter browser number",
                    default=1,
                    choices=[str(i) for i in range(1, len(available_browsers) + 1)],
                )
                browser = available_browsers[choice - 1]
        else:
            print_warning("No browsers detected for cookie extraction")
            browser = AppConfig.get_default_browser()

    # Execute download
    success = download_youtube(url, output_dir, browser, verbose)
    return 0 if success else 1


# ----------------------------------------------------------------
# Menu Functions
# ----------------------------------------------------------------
def create_download_options_table() -> Table:
    """
    Create a table showing download options.

    Returns:
        Rich Table object with download options
    """
    table = Table(
        show_header=True,
        header_style=f"bold {NordColors.FROST_1}",
        expand=True,
        title=f"[bold {NordColors.FROST_2}]Download Options[/]",
        border_style=NordColors.FROST_3,
        title_justify="center",
    )

    table.add_column("#", style=f"bold {NordColors.FROST_4}", justify="right", width=4)
    table.add_column("Type", style=f"bold {NordColors.FROST_2}")
    table.add_column("Description", style=f"{NordColors.SNOW_STORM_1}")
    table.add_column("Status", style=f"bold {NordColors.GREEN}")

    # Check dependency status
    file_deps = check_dependencies(DEPENDENCY_GROUPS["file"])
    file_status = (
        "✓ Available" if all(file_deps.values()) else "⚠ Missing some dependencies"
    )

    youtube_deps = check_dependencies(DEPENDENCY_GROUPS["youtube"])
    youtube_status = (
        "✓ Available" if all(youtube_deps.values()) else "⚠ Missing dependencies"
    )

    table.add_row("1", "File Download", "Download any file from the web", file_status)
    table.add_row(
        "2", "YouTube", "Download videos or playlists from YouTube", youtube_status
    )
    table.add_row("3", "Settings", "Configure application settings", "")
    table.add_row("4", "Exit", "Quit the application", "")

    return table


def create_system_info_table() -> Table:
    """
    Create a table with system information.

    Returns:
        Rich Table object with system information
    """
    table = Table(
        show_header=True,
        header_style=f"bold {NordColors.FROST_1}",
        expand=True,
        title=f"[bold {NordColors.FROST_2}]System Information[/]",
        border_style=NordColors.FROST_3,
        title_justify="center",
    )

    table.add_column("Property", style=f"bold {NordColors.FROST_2}")
    table.add_column("Value", style=f"{NordColors.SNOW_STORM_1}")

    table.add_row("OS", f"{platform.system()} {platform.release()}")
    table.add_row("Python", f"{platform.python_version()}")
    table.add_row("User", os.environ.get("USER", os.environ.get("USERNAME", "unknown")))
    table.add_row("Hostname", AppConfig.HOSTNAME)
    table.add_row("Default Download Dir", AppConfig.DEFAULT_DOWNLOAD_DIR)
    table.add_row("Admin/Root", "Yes" if is_admin_or_root() else "No")

    return table


def create_dependencies_table() -> Table:
    """
    Create a table with dependency status.

    Returns:
        Rich Table object with dependency status
    """
    table = Table(
        show_header=True,
        header_style=f"bold {NordColors.FROST_1}",
        expand=True,
        title=f"[bold {NordColors.FROST_2}]Dependencies[/]",
        border_style=NordColors.FROST_3,
        title_justify="center",
    )

    table.add_column("Name", style=f"bold {NordColors.FROST_2}")
    table.add_column("Status", style=f"{NordColors.SNOW_STORM_1}")
    table.add_column("Required For", style=f"{NordColors.FROST_4}")

    # All unique dependencies
    all_deps = set()
    for group in DEPENDENCY_GROUPS.values():
        all_deps.update(group)

    # Map each dependency to the features that require it
    dep_features = {}
    for dep in all_deps:
        features = []
        for feature, deps in DEPENDENCY_GROUPS.items():
            if dep in deps:
                features.append(feature)
        dep_features[dep] = features

    # Check status of each dependency
    dep_status = check_dependencies(list(all_deps))

    # Add rows to the table
    for dep_name in sorted(all_deps):
        status_text = (
            "✓ Installed" if dep_status.get(dep_name, False) else "✗ Not Installed"
        )
        status_style = (
            NordColors.GREEN if dep_status.get(dep_name, False) else NordColors.RED
        )
        features_text = ", ".join(dep_features.get(dep_name, []))

        table.add_row(
            DEPENDENCY_DEFINITIONS[dep_name].display_name,
            f"[{status_style}]{status_text}[/]",
            features_text,
        )

    return table


def download_menu() -> None:
    """
    Interactive download menu for the Universal Downloader.
    """
    while True:
        console.clear()
        console.print(create_header())

        # Display current time and system info
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        console.print(
            Align.center(
                f"[{NordColors.SNOW_STORM_1}]System: {platform.system()} {platform.release()}[/] | "
                f"[{NordColors.SNOW_STORM_1}]Time: {current_time}[/]"
            )
        )
        console.print()

        # Display download options
        console.print(create_download_options_table())
        console.print()

        # Get user choice
        choice = Prompt.ask(
            f"[bold {NordColors.PURPLE}]Enter your choice",
            choices=["1", "2", "3", "4"],
            default="1",
        )

        if choice == "1":  # File download
            console.clear()
            console.print(create_header())
            display_panel("File Download", style=NordColors.FROST_3, title="Mode")

            url = Prompt.ask(f"[bold {NordColors.PURPLE}]Enter URL to download")
            if not url:
                print_error("URL cannot be empty")
                input("Press Enter to continue...")
                continue

            output_dir = Prompt.ask(
                f"[bold {NordColors.PURPLE}]Enter output directory",
                default=AppConfig.DEFAULT_DOWNLOAD_DIR,
            )

            verbose = Confirm.ask(
                f"[bold {NordColors.PURPLE}]Enable verbose output?", default=False
            )

            cmd_file_download(url, output_dir, verbose)
            input("\nPress Enter to return to the main menu...")

        elif choice == "2":  # YouTube download
            console.clear()
            console.print(create_header())
            display_panel("YouTube Download", style=NordColors.FROST_3, title="Mode")

            url = Prompt.ask(f"[bold {NordColors.PURPLE}]Enter YouTube URL")
            if not url:
                print_error("URL cannot be empty")
                input("Press Enter to continue...")
                continue

            output_dir = Prompt.ask(
                f"[bold {NordColors.PURPLE}]Enter output directory",
                default=AppConfig.DEFAULT_DOWNLOAD_DIR,
            )

            # Browser selection
            browsers = AppConfig.get_browser_list()
            console.print(f"\n[bold {NordColors.FROST_2}]Available browsers:[/]")
            for i, browser in enumerate(browsers, 1):
                console.print(f"  {i}. {browser}")

            browser_choice = IntPrompt.ask(
                f"[bold {NordColors.PURPLE}]Select browser for cookies",
                default=1,
                choices=[str(i) for i in range(1, len(browsers) + 1)],
            )
            selected_browser = browsers[browser_choice - 1]

            verbose = Confirm.ask(
                f"[bold {NordColors.PURPLE}]Enable verbose output?", default=False
            )

            cmd_youtube_download(url, output_dir, selected_browser, verbose)
            input("\nPress Enter to return to the main menu...")

        elif choice == "3":  # Settings
            console.clear()
            console.print(create_header())
            display_panel(
                "Settings & Information",
                style=NordColors.FROST_3,
                title="Configuration",
            )

            # Display system information
            console.print(create_system_info_table())
            console.print()

            # Display dependency status
            console.print(create_dependencies_table())
            console.print()

            # Options for settings
            console.print(f"[bold {NordColors.FROST_2}]Settings Options:[/]")
            console.print(f"  1. Install missing dependencies")
            console.print(f"  2. Return to main menu")
            console.print()

            settings_choice = Prompt.ask(
                f"[bold {NordColors.PURPLE}]Select option",
                choices=["1", "2"],
                default="2",
            )

            if settings_choice == "1":
                # Collect all unique dependencies
                all_deps = set()
                for deps in DEPENDENCY_GROUPS.values():
                    all_deps.update(deps)

                dep_status = check_dependencies(list(all_deps))
                missing_deps = [
                    dep for dep, installed in dep_status.items() if not installed
                ]

                if missing_deps:
                    print_step(f"Found {len(missing_deps)} missing dependencies:")
                    for dep in missing_deps:
                        print_message(
                            f"{DEPENDENCY_DEFINITIONS[dep].display_name}",
                            NordColors.YELLOW,
                        )

                    if Confirm.ask("Install missing dependencies?", default=True):
                        install_dependencies(missing_deps, verbose=True)
                    else:
                        print_message("Installation cancelled", NordColors.YELLOW)
                else:
                    print_success("All dependencies are installed!")

                input("\nPress Enter to continue...")

        elif choice == "4":  # Exit
            console.clear()
            console.print(
                Panel(
                    Text(
                        "Thank you for using Universal Downloader!",
                        style=f"bold {NordColors.FROST_2}",
                    ),
                    border_style=Style(color=NordColors.FROST_1),
                    padding=(1, 2),
                )
            )
            break

        else:
            print_error("Invalid selection. Please choose 1-4.")
            input("Press Enter to continue...")


def show_usage() -> None:
    """
    Display usage information for the script.
    """
    console.print(create_header())

    # Create a usage table
    table = Table(
        show_header=True,
        header_style=f"bold {NordColors.FROST_1}",
        expand=True,
        title=f"[bold {NordColors.FROST_2}]Usage Information[/]",
        border_style=NordColors.FROST_3,
        title_justify="center",
    )

    table.add_column("Command", style=f"bold {NordColors.FROST_2}")
    table.add_column("Description", style=f"{NordColors.SNOW_STORM_1}")

    table.add_row("./universal_downloader.py", "Start the interactive download menu")
    table.add_row(
        "./universal_downloader.py file <url> [options]", "Download a file from the web"
    )
    table.add_row(
        "./universal_downloader.py youtube <url> [options]",
        "Download YouTube video/playlist",
    )
    table.add_row("./universal_downloader.py help", "Show this help information")

    console.print(table)

    # Options table
    options_table = Table(
        show_header=True,
        header_style=f"bold {NordColors.FROST_1}",
        expand=True,
        title=f"[bold {NordColors.FROST_2}]Options[/]",
        border_style=NordColors.FROST_3,
        title_justify="center",
    )

    options_table.add_column("Option", style=f"bold {NordColors.FROST_2}")
    options_table.add_column("Description", style=f"{NordColors.SNOW_STORM_1}")

    options_table.add_row(
        "-o, --output-dir <dir>",
        f"Set the output directory (default: {AppConfig.DEFAULT_DOWNLOAD_DIR})",
    )
    options_table.add_row("-v, --verbose", "Enable verbose output")
    options_table.add_row(
        "-b, --browser <browser>", "Browser to use for YouTube cookies"
    )

    console.print(options_table)

    # Examples
    examples_table = Table(
        show_header=True,
        header_style=f"bold {NordColors.FROST_1}",
        expand=True,
        title=f"[bold {NordColors.FROST_2}]Examples[/]",
        border_style=NordColors.FROST_3,
        title_justify="center",
    )

    examples_table.add_column(
        "Example", style=f"bold {NordColors.FROST_2}", no_wrap=True
    )
    examples_table.add_column("Description", style=f"{NordColors.SNOW_STORM_1}")

    examples_table.add_row("./universal_downloader.py", "Start the interactive menu")
    examples_table.add_row(
        "./universal_downloader.py file https://example.com/file.zip -o /tmp",
        "Download a zip file to /tmp directory",
    )
    examples_table.add_row(
        "./universal_downloader.py youtube https://youtube.com/watch?v=abcdef -b chrome",
        "Download a YouTube video using Chrome cookies",
    )

    console.print(examples_table)


# ----------------------------------------------------------------
# Command Line Argument Parsing
# ----------------------------------------------------------------
def parse_args() -> Dict[str, Any]:
    """
    Parse command-line arguments.

    Returns:
        Dictionary with parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Universal Downloader - Download files and media with style",
        add_help=False,  # We'll handle help manually for better styling
    )

    # Basic commands
    parser.add_argument(
        "command",
        nargs="?",
        choices=["file", "youtube", "help"],
        default="menu",
        help="Command to execute",
    )

    # URL argument
    parser.add_argument("url", nargs="?", help="URL to download")

    # Common options
    parser.add_argument(
        "-o",
        "--output-dir",
        default=AppConfig.DEFAULT_DOWNLOAD_DIR,
        help=f"Output directory (default: {AppConfig.DEFAULT_DOWNLOAD_DIR})",
    )

    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose output"
    )

    parser.add_argument("-b", "--browser", help="Browser to use for YouTube cookies")

    parser.add_argument(
        "-h", "--help", action="store_true", help="Show help information"
    )

    # Parse the arguments
    args = vars(parser.parse_args())

    # Check if help was requested
    if args.get("help", False):
        args["command"] = "help"

    # Validate command-specific arguments
    if args["command"] in ["file", "youtube"] and not args["url"]:
        print_error(f"URL is required for '{args['command']}' command")
        args["command"] = "help"

    return args


# ----------------------------------------------------------------
# Main Entry Point
# ----------------------------------------------------------------
def main() -> None:
    """
    Main function: parses arguments, checks dependencies, and dispatches commands.
    """
    try:
        # Setup logging
        setup_logging()

        # Parse command-line arguments
        args = parse_args()
        command = args.get("command", "menu")

        if command == "help":
            show_usage()
            sys.exit(0)

        # Display the header
        console.print(create_header())

        # System information
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        console.print(
            Align.center(
                f"[{NordColors.SNOW_STORM_1}]System: {platform.system()} {platform.release()}[/] | "
                f"[{NordColors.SNOW_STORM_1}]Time: {current_time}[/]"
            )
        )
        console.print()

        # Check internet connectivity
        check_internet_connectivity()

        # Dispatch command
        if command == "menu":
            download_menu()
        elif command == "file":
            exit_code = cmd_file_download(
                args["url"], args["output_dir"], args["verbose"]
            )
            sys.exit(exit_code)
        elif command == "youtube":
            exit_code = cmd_youtube_download(
                args["url"], args["output_dir"], args["browser"], args["verbose"]
            )
            sys.exit(exit_code)
        else:
            print_error(f"Unknown command: {command}")
            show_usage()
            sys.exit(1)

    except KeyboardInterrupt:
        print_warning("\nProcess interrupted by user")
        sys.exit(130)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        console.print_exception()
        sys.exit(1)


if __name__ == "__main__":
    main()
