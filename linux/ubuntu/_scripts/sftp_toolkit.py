#!/usr/bin/env python3
"""
SFTP Toolkit
--------------------------------------------------
A fully interactive, menu-driven SFTP toolkit for performing
SFTP file transfer operations with a production-grade, polished
CLI that integrates prompt_toolkit for auto-completion, Rich for
stylish output, and Pyfiglet for dynamic ASCII banners.

Features:
  • Interactive, menu-driven interface with dynamic ASCII banners.
  • SFTP operations including manual connection, device-based connection,
    directory listing, file upload/download, deletion, renaming, and remote
    directory management.
  • Predefined device lists (Tailscale and local) for quick connection setup.
  • Real-time progress tracking during file transfers.
  • Robust error handling and cross-platform compatibility.
  • Fully integrated prompt_toolkit auto-completion for both local and remote
    file/directory selection.
  • Nord-themed color styling throughout the application.

Version: 2.0.0
"""

# ----------------------------------------------------------------
# Dependency Check and Imports
# ----------------------------------------------------------------
import atexit
import os
import sys
import time
import socket
import getpass
import platform
import signal
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any, Callable


# Function to install dependencies for non-root user when script is run with sudo
def install_dependencies():
    """Install required dependencies for the non-root user when run with sudo."""
    required_packages = ["paramiko", "rich", "pyfiglet", "prompt_toolkit"]

    # Get actual user when script is run with sudo
    user = os.environ.get("SUDO_USER", os.environ.get("USER", getpass.getuser()))

    # Don't proceed if we're not running as sudo
    if os.geteuid() != 0:
        print(f"Installing dependencies for user: {user}")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--user"] + required_packages
        )
        return

    # We're running as sudo - install for the real user
    print(f"Running as sudo. Installing dependencies for user: {user}")
    real_user_home = os.path.expanduser(f"~{user}")

    try:
        # Run pip install as the real user
        subprocess.check_call(
            ["sudo", "-u", user, sys.executable, "-m", "pip", "install", "--user"]
            + required_packages
        )

        print(f"Successfully installed dependencies for user: {user}")
    except subprocess.CalledProcessError as e:
        print(f"Failed to install dependencies: {e}")
        sys.exit(1)


# Try to import dependencies, install if missing
try:
    import paramiko
    import pyfiglet
    from rich.console import Console
    from rich.text import Text
    from rich.table import Table
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm, IntPrompt
    from rich.progress import (
        Progress,
        SpinnerColumn,
        TextColumn,
        BarColumn,
        TaskProgressColumn,
        TimeRemainingColumn,
        DownloadColumn,
    )
    from rich.align import Align
    from rich.style import Style
    from rich.columns import Columns
    from rich.traceback import install as install_rich_traceback

    from prompt_toolkit import prompt as pt_prompt
    from prompt_toolkit.completion import PathCompleter, Completer, Completion
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory

except ImportError:
    print("Required libraries not found. Installing dependencies...")
    install_dependencies()

    # Re-execute the script after installing dependencies
    print("Dependencies installed successfully. Restarting script...")
    os.execv(sys.executable, [sys.executable] + sys.argv)

# Install rich traceback handler for better error display
install_rich_traceback(show_locals=True)

# ----------------------------------------------------------------
# Configuration & Constants
# ----------------------------------------------------------------
HOSTNAME: str = socket.gethostname()
DEFAULT_USERNAME: str = (
    os.environ.get("SUDO_USER") or os.environ.get("USER") or getpass.getuser()
)
SFTP_DEFAULT_PORT: int = 22
VERSION: str = "2.0.0"
APP_NAME: str = "SFTP Toolkit"
APP_SUBTITLE: str = "Advanced File Transfer Manager"

# Default local folder for all file operations - Use user's home directory
if os.environ.get("SUDO_USER"):
    # If running with sudo, get the real user's home directory
    DEFAULT_LOCAL_FOLDER = os.path.expanduser(
        f"~{os.environ.get('SUDO_USER')}/Downloads"
    )
else:
    DEFAULT_LOCAL_FOLDER = os.path.expanduser("~/Downloads")

# Set up history file in user's home directory
HISTORY_DIR = os.path.expanduser(
    f"~{os.environ.get('SUDO_USER', DEFAULT_USERNAME)}/.sftp_toolkit"
)
os.makedirs(HISTORY_DIR, exist_ok=True)
COMMAND_HISTORY = os.path.join(HISTORY_DIR, "command_history")
PATH_HISTORY = os.path.join(HISTORY_DIR, "path_history")

# Ensure the history files exist
for history_file in [COMMAND_HISTORY, PATH_HISTORY]:
    if not os.path.exists(history_file):
        with open(history_file, "w") as f:
            pass


# ----------------------------------------------------------------
# Nord-Themed Colors
# ----------------------------------------------------------------
class NordColors:
    POLAR_NIGHT_1: str = "#2E3440"
    POLAR_NIGHT_2: str = "#3B4252"
    POLAR_NIGHT_3: str = "#434C5E"
    POLAR_NIGHT_4: str = "#4C566A"
    SNOW_STORM_1: str = "#D8DEE9"
    SNOW_STORM_2: str = "#E5E9F0"
    SNOW_STORM_3: str = "#ECEFF4"
    FROST_1: str = "#8FBCBB"
    FROST_2: str = "#88C0D0"
    FROST_3: str = "#81A1C1"
    FROST_4: str = "#5E81AC"
    RED: str = "#BF616A"
    ORANGE: str = "#D08770"
    YELLOW: str = "#EBCB8B"
    GREEN: str = "#A3BE8C"
    PURPLE: str = "#B48EAD"


# ----------------------------------------------------------------
# Initialize Rich Console
# ----------------------------------------------------------------
console: Console = Console()


# ----------------------------------------------------------------
# Data Structures
# ----------------------------------------------------------------
@dataclass
class Device:
    """
    Represents an SFTP-accessible device with connection details.
    """

    name: str
    ip_address: str
    description: str
    port: int = SFTP_DEFAULT_PORT
    favorite: bool = False
    last_connected: Optional[datetime] = None

    def get_favorite_indicator(self) -> str:
        """Return a star indicator if the device is marked as favorite."""
        return "★ " if self.favorite else ""


@dataclass
class SFTPConnection:
    """
    Maintains the state of an SFTP connection.
    """

    sftp: Optional[paramiko.SFTPClient] = None
    transport: Optional[paramiko.Transport] = None
    hostname: Optional[str] = None
    username: Optional[str] = None
    port: int = SFTP_DEFAULT_PORT
    connected_at: Optional[datetime] = None

    def is_connected(self) -> bool:
        """Check if there is an active SFTP connection."""
        return (
            self.sftp is not None
            and self.transport is not None
            and self.transport.is_active()
        )

    def get_connection_info(self) -> str:
        """Return formatted connection information."""
        if not self.is_connected():
            return "Not connected"

        connected_time = ""
        if self.connected_at:
            connected_time = (
                f"Connected at: {self.connected_at.strftime('%Y-%m-%d %H:%M:%S')}"
            )

        return f"{self.username}@{self.hostname}:{self.port} | {connected_time}"


# Global SFTP connection object
sftp_connection = SFTPConnection()


# ----------------------------------------------------------------
# Custom Remote Path Completer
# ----------------------------------------------------------------
class RemotePathCompleter(Completer):
    """
    Completer for remote file paths using the active SFTP client.
    This completer lists files in the specified remote base directory.
    """

    def __init__(self, sftp_client, base_path="."):
        self.sftp = sftp_client
        self.base_path = base_path

    def get_completions(self, document, complete_event):
        text = document.text
        path = text

        # Handle relative paths
        if not text or text == ".":
            dir_path = self.base_path
            prefix = ""
        elif "/" in text:
            dir_path = os.path.dirname(text) or "."
            prefix = os.path.basename(text)
        else:
            dir_path = self.base_path
            prefix = text

        try:
            # List directory contents
            files = self.sftp.listdir(dir_path)

            # Get stats to show directories with trailing slash
            for filename in files:
                if not filename.startswith(prefix):
                    continue

                full_path = os.path.join(dir_path, filename)
                try:
                    attrs = self.sftp.stat(full_path)
                    is_dir = attrs.st_mode & 0o40000  # Check if it's a directory

                    # For display - add trailing slash for directories
                    display = filename + ("/" if is_dir else "")

                    # Yield the completion
                    yield Completion(
                        filename,
                        start_position=-len(prefix),
                        display=display,
                        style="bg:#3B4252 fg:#A3BE8C"
                        if is_dir
                        else "bg:#3B4252 fg:#88C0D0",
                    )
                except Exception:
                    # Skip files that can't be stat'd
                    continue
        except Exception as e:
            # If we can't list the directory, don't provide completions
            console.print(
                f"[dim {NordColors.RED}]Error listing remote directory: {e}[/]"
            )


# ----------------------------------------------------------------
# UI Helper Functions
# ----------------------------------------------------------------
def create_header() -> Panel:
    """
    Generate an ASCII art header with dynamic gradient styling using Pyfiglet.
    """
    fonts = ["slant", "big", "digital", "standard", "small"]
    ascii_art = ""

    for font in fonts:
        try:
            fig = pyfiglet.Figlet(font=font, width=60)
            ascii_art = fig.renderText(APP_NAME)
            if ascii_art.strip():
                break
        except Exception:
            continue

    ascii_lines = [line for line in ascii_art.splitlines() if line.strip()]
    colors = [
        NordColors.FROST_1,
        NordColors.FROST_2,
        NordColors.FROST_3,
        NordColors.FROST_4,
    ]

    styled_text = ""
    for i, line in enumerate(ascii_lines):
        color = colors[i % len(colors)]
        # Escape any square brackets in the ASCII art to prevent markup issues
        escaped_line = line.replace("[", "\\[").replace("]", "\\]")
        styled_text += f"[bold {color}]{escaped_line}[/]\n"

    border = f"[{NordColors.FROST_3}]{'━' * 60}[/]"
    styled_text = border + "\n" + styled_text + border

    header_panel = Panel(
        Text.from_markup(styled_text),
        border_style=Style(color=NordColors.FROST_1),
        padding=(1, 2),
        title=f"[bold {NordColors.SNOW_STORM_2}]v{VERSION}[/]",
        title_align="right",
        subtitle=f"[bold {NordColors.SNOW_STORM_1}]{APP_SUBTITLE}[/]",
        subtitle_align="center",
    )

    return header_panel


def print_message(
    text: str, style: str = NordColors.FROST_2, prefix: str = "•"
) -> None:
    """Print a styled message with a prefix."""
    console.print(f"[{style}]{prefix} {text}[/{style}]")


def print_success(message: str) -> None:
    """Print a success message."""
    print_message(message, NordColors.GREEN, "✓")


def print_warning(message: str) -> None:
    """Print a warning message."""
    print_message(message, NordColors.YELLOW, "⚠")


def print_error(message: str) -> None:
    """Print an error message."""
    print_message(message, NordColors.RED, "✗")


def print_step(message: str) -> None:
    """Print a step message."""
    print_message(message, NordColors.FROST_2, "→")


def display_panel(
    message: str, style: str = NordColors.FROST_2, title: Optional[str] = None
) -> None:
    """Display a message in a styled Rich panel."""
    panel = Panel(
        Text.from_markup(f"[{style}]{message}[/]"),
        border_style=Style(color=style),
        padding=(1, 2),
        title=f"[bold {style}]{title}[/]" if title else None,
    )
    console.print(panel)


def print_section(title: str) -> None:
    """Print a section header."""
    console.print()
    console.print(f"[bold {NordColors.FROST_3}]{title}[/]")
    console.print(f"[{NordColors.FROST_3}]{'─' * len(title)}[/]")
    console.print()


def show_help() -> None:
    """Display help information."""
    help_text = f"""
[bold]Available Commands:[/]

[bold {NordColors.FROST_2}]1-9, A, 0[/]:   Menu selection numbers
[bold {NordColors.FROST_2}]Tab[/]:         Auto-complete file paths and commands
[bold {NordColors.FROST_2}]Up/Down[/]:     Navigate command history
[bold {NordColors.FROST_2}]Ctrl+C[/]:      Cancel current operation
[bold {NordColors.FROST_2}]h[/]:           Show this help screen
"""
    console.print(
        Panel(
            Text.from_markup(help_text),
            title=f"[bold {NordColors.FROST_1}]Help & Commands[/]",
            border_style=Style(color=NordColors.FROST_3),
            padding=(1, 2),
        )
    )


# ----------------------------------------------------------------
# Environment Loader and SSH Key Helper Functions
# ----------------------------------------------------------------
def load_env() -> Dict[str, str]:
    """
    Load environment variables from a ".env" file.
    Expected format: SSH_KEY_PASSWORD="your_key_password"
    """
    env_vars = {}
    env_file = os.path.join(HISTORY_DIR, ".env")

    try:
        if os.path.exists(env_file):
            with open(env_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        env_vars[key.strip()] = value.strip().strip('"').strip("'")
                        # Also set in environment for this process
                        os.environ[key.strip()] = value.strip().strip('"').strip("'")
    except Exception as e:
        console.print(f"[bold {NordColors.RED}]Error loading .env file: {e}[/]")

    return env_vars


def get_default_username() -> str:
    """
    Return the default username. If run with sudo, use the original user's username.
    """
    return os.environ.get("SUDO_USER") or os.environ.get("USER") or getpass.getuser()


def get_ssh_key_path() -> str:
    """Get the path to the user's SSH private key."""
    # If running with sudo, use the actual user's home directory
    if os.environ.get("SUDO_USER"):
        return os.path.expanduser(f"~{os.environ.get('SUDO_USER')}/.ssh/id_rsa")
    else:
        return os.path.expanduser("~/.ssh/id_rsa")


def load_private_key():
    """
    Load the default SSH private key.
    If the key is encrypted, use SSH_KEY_PASSWORD from environment.
    """
    key_path = get_ssh_key_path()

    try:
        key = paramiko.RSAKey.from_private_key_file(key_path)
        return key
    except paramiko.PasswordRequiredException:
        # Try to get the key password from environment
        key_password = os.environ.get("SSH_KEY_PASSWORD")

        if not key_password:
            # Prompt for password if not in environment
            key_password = pt_prompt(
                f"[bold {NordColors.PURPLE}]Enter SSH key password: [/]",
                is_password=True,
            )

            # Save to environment for future use in this session
            os.environ["SSH_KEY_PASSWORD"] = key_password

        try:
            key = paramiko.RSAKey.from_private_key_file(key_path, password=key_password)
            return key
        except Exception as e:
            console.print(
                f"[bold {NordColors.RED}]Error loading private key with passphrase: {e}[/]"
            )
            return None
    except Exception as e:
        console.print(f"[bold {NordColors.RED}]Error loading private key: {e}[/]")
        return None


# ----------------------------------------------------------------
# Signal Handling and Cleanup
# ----------------------------------------------------------------
def cleanup() -> None:
    """Perform cleanup tasks before exiting."""
    print_message("Cleaning up session resources...", NordColors.FROST_3)

    # Close SFTP connection if open
    if sftp_connection.is_connected():
        disconnect_sftp()


def signal_handler(sig: int, frame: Any) -> None:
    """Handle termination signals gracefully."""
    try:
        sig_name = signal.Signals(sig).name
        print_warning(f"Process interrupted by {sig_name}")
    except Exception:
        print_warning(f"Process interrupted by signal {sig}")

    cleanup()
    sys.exit(128 + sig)


# Register signal handlers and cleanup
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
atexit.register(cleanup)


# ----------------------------------------------------------------
# Device Data Functions
# ----------------------------------------------------------------
def load_tailscale_devices() -> List[Device]:
    """Load preset Tailscale devices."""
    return [
        Device(
            name="ubuntu-server",
            ip_address="100.109.43.88",
            description="Primary Ubuntu Server",
        ),
        Device(
            name="ubuntu-lenovo",
            ip_address="100.66.213.7",
            description="Development Laptop",
        ),
        Device(
            name="raspberrypi-5",
            ip_address="100.105.117.18",
            description="Raspberry Pi 5",
        ),
        Device(
            name="raspberrypi-3",
            ip_address="100.116.191.42",
            description="Raspberry Pi 3",
        ),
        Device(
            name="ubuntu-server-vm-01",
            ip_address="100.84.119.114",
            description="Ubuntu VM 1",
        ),
        Device(
            name="ubuntu-server-vm-02",
            ip_address="100.122.237.56",
            description="Ubuntu VM 2",
        ),
        Device(
            name="ubuntu-server-vm-03",
            ip_address="100.97.229.120",
            description="Ubuntu VM 3",
        ),
        Device(
            name="ubuntu-server-vm-04",
            ip_address="100.73.171.7",
            description="Ubuntu VM 4",
        ),
        Device(
            name="ubuntu-lenovo-vm-01",
            ip_address="100.107.79.81",
            description="Lenovo VM 1",
        ),
        Device(
            name="ubuntu-lenovo-vm-02",
            ip_address="100.78.101.2",
            description="Lenovo VM 2",
        ),
        Device(
            name="ubuntu-lenovo-vm-03",
            ip_address="100.95.115.62",
            description="Lenovo VM 3",
        ),
        Device(
            name="ubuntu-lenovo-vm-04",
            ip_address="100.92.31.94",
            description="Lenovo VM 4",
        ),
    ]


def load_local_devices() -> List[Device]:
    """Load preset local network devices."""
    return [
        Device(
            name="ubuntu-server",
            ip_address="192.168.0.73",
            description="Primary Server (LAN)",
        ),
        Device(
            name="ubuntu-lenovo",
            ip_address="192.168.0.31",
            description="Development Laptop (LAN)",
        ),
        Device(
            name="raspberrypi-5",
            ip_address="192.168.0.40",
            description="Raspberry Pi 5 (LAN)",
        ),
        Device(
            name="raspberrypi-3",
            ip_address="192.168.0.100",
            description="Raspberry Pi 3 (LAN)",
        ),
    ]


def select_device_menu() -> Device:
    """
    Display a device selection menu for choosing Tailscale or local devices.
    Returns the selected device.
    """
    console.print(
        Panel(f"[bold {NordColors.FROST_2}]Select Device Type[/]", expand=False)
    )

    device_type = Prompt.ask(
        f"[bold {NordColors.PURPLE}]Choose device type[/]",
        choices=["tailscale", "local"],
        default="local",
    )

    devices = (
        load_tailscale_devices() if device_type == "tailscale" else load_local_devices()
    )

    table = Table(
        title=f"Available {device_type.capitalize()} Devices",
        show_header=True,
        header_style=f"bold {NordColors.FROST_3}",
    )

    table.add_column("No.", style="bold", width=4)
    table.add_column("Name", style="bold")
    table.add_column("IP Address", style=f"bold {NordColors.GREEN}")
    table.add_column("Description", style="italic")

    for idx, device in enumerate(devices, start=1):
        table.add_row(
            str(idx),
            f"{device.get_favorite_indicator()}{device.name}",
            device.ip_address,
            device.description,
        )

    console.print(table)

    choice = IntPrompt.ask(
        f"[bold {NordColors.PURPLE}]Select device number[/]", default=1
    )

    try:
        selected_device = devices[choice - 1]
    except (IndexError, TypeError):
        console.print(
            f"[bold {NordColors.RED}]Invalid selection. Defaulting to device 1.[/]"
        )
        selected_device = devices[0]

    console.print(
        f"[bold {NordColors.GREEN}]Selected device:[/] {selected_device.name} ({selected_device.ip_address})"
    )

    return selected_device


# ----------------------------------------------------------------
# SFTP Connection Operations
# ----------------------------------------------------------------
def connect_sftp() -> bool:
    """
    Establish an SFTP connection using key-based authentication.
    Prompts for hostname, port, and username.
    Returns True if connection is successful, False otherwise.
    """
    console.print(
        Panel(f"[bold {NordColors.FROST_2}]SFTP Connection Setup[/]", expand=False)
    )

    # Use history for hostname
    hostname = pt_prompt(
        f"[bold {NordColors.PURPLE}]Enter SFTP Hostname: [/]",
        history=FileHistory(COMMAND_HISTORY),
        auto_suggest=AutoSuggestFromHistory(),
    )

    port = IntPrompt.ask(
        f"[bold {NordColors.PURPLE}]Enter Port[/]", default=SFTP_DEFAULT_PORT
    )

    username = pt_prompt(
        f"[bold {NordColors.PURPLE}]Enter Username: [/]",
        default=get_default_username(),
        history=FileHistory(COMMAND_HISTORY),
        auto_suggest=AutoSuggestFromHistory(),
    )

    key = load_private_key()
    if key is None:
        console.print(
            f"[bold {NordColors.RED}]Could not load SSH private key. Connection aborted.[/]"
        )
        return False

    try:
        with Progress(
            SpinnerColumn("dots", style=f"bold {NordColors.FROST_1}"),
            TextColumn("[bold {task.fields[message_color]}]{task.fields[message]}"),
            console=console,
        ) as progress:
            task = progress.add_task(
                "Connecting...",
                message="Initializing secure channel...",
                message_color=NordColors.FROST_2,
            )

            # Create transport and connect
            transport = paramiko.Transport((hostname, port))
            progress.update(
                task,
                message="Negotiating encryption parameters...",
                message_color=NordColors.FROST_2,
            )

            transport.connect(username=username, pkey=key)
            progress.update(
                task,
                message=f"Establishing SFTP connection to {hostname}...",
                message_color=NordColors.FROST_2,
            )

            # Create SFTP client
            sftp = paramiko.SFTPClient.from_transport(transport)
            progress.update(
                task,
                message="Connection established successfully!",
                message_color=NordColors.GREEN,
            )
            time.sleep(0.5)

        # Update global connection object
        sftp_connection.sftp = sftp
        sftp_connection.transport = transport
        sftp_connection.hostname = hostname
        sftp_connection.username = username
        sftp_connection.port = port
        sftp_connection.connected_at = datetime.now()

        console.print(
            f"[bold {NordColors.GREEN}]Successfully connected to SFTP server using key-based authentication.[/]"
        )
        return True

    except Exception as e:
        console.print(f"[bold {NordColors.RED}]Error connecting to SFTP server: {e}[/]")
        return False


def connect_sftp_device(device: Device) -> bool:
    """
    Establish an SFTP connection using a predefined device.
    The device's IP address is used as the hostname.
    Returns True if connection is successful, False otherwise.
    """
    console.print(
        Panel(
            f"[bold {NordColors.FROST_2}]Connecting to {device.name} ({device.ip_address})[/]",
            expand=False,
        )
    )

    port = IntPrompt.ask(
        f"[bold {NordColors.PURPLE}]Enter Port[/]", default=device.port
    )

    username = pt_prompt(
        f"[bold {NordColors.PURPLE}]Enter Username: [/]",
        default=get_default_username(),
        history=FileHistory(COMMAND_HISTORY),
        auto_suggest=AutoSuggestFromHistory(),
    )

    key = load_private_key()
    if key is None:
        console.print(
            f"[bold {NordColors.RED}]Could not load SSH private key. Connection aborted.[/]"
        )
        return False

    try:
        with Progress(
            SpinnerColumn("dots", style=f"bold {NordColors.FROST_1}"),
            TextColumn("[bold {task.fields[message_color]}]{task.fields[message]}"),
            console=console,
        ) as progress:
            task = progress.add_task(
                "Connecting...",
                message="Initializing secure channel...",
                message_color=NordColors.FROST_2,
            )

            # Create transport and connect
            transport = paramiko.Transport((device.ip_address, port))
            progress.update(
                task,
                message="Negotiating encryption parameters...",
                message_color=NordColors.FROST_2,
            )

            transport.connect(username=username, pkey=key)
            progress.update(
                task,
                message=f"Establishing SFTP connection to {device.name}...",
                message_color=NordColors.FROST_2,
            )

            # Create SFTP client
            sftp = paramiko.SFTPClient.from_transport(transport)
            progress.update(
                task,
                message="Connection established successfully!",
                message_color=NordColors.GREEN,
            )
            time.sleep(0.5)

        # Update global connection object
        sftp_connection.sftp = sftp
        sftp_connection.transport = transport
        sftp_connection.hostname = device.ip_address
        sftp_connection.username = username
        sftp_connection.port = port
        sftp_connection.connected_at = datetime.now()

        # Record connection
        device.last_connected = datetime.now()

        console.print(
            f"[bold {NordColors.GREEN}]Successfully connected to {device.name} using key-based authentication.[/]"
        )
        return True

    except Exception as e:
        console.print(
            f"[bold {NordColors.RED}]Error connecting to {device.name}: {e}[/]"
        )
        return False


def disconnect_sftp() -> None:
    """Disconnect from the SFTP server and close connections."""
    if not sftp_connection.is_connected():
        console.print(f"[bold {NordColors.YELLOW}]Not currently connected.[/]")
        return

    try:
        with Progress(
            SpinnerColumn("dots", style=f"bold {NordColors.FROST_1}"),
            TextColumn("[bold {task.fields[message_color]}]{task.fields[message]}"),
            console=console,
        ) as progress:
            task = progress.add_task(
                "Disconnecting...",
                message="Closing SFTP channel...",
                message_color=NordColors.FROST_2,
            )

            if sftp_connection.sftp:
                sftp_connection.sftp.close()

            progress.update(
                task,
                message="Terminating transport...",
                message_color=NordColors.FROST_2,
            )

            if sftp_connection.transport:
                sftp_connection.transport.close()

            progress.update(
                task,
                message="Connection closed successfully",
                message_color=NordColors.GREEN,
            )
            time.sleep(0.5)

        # Reset connection object
        sftp_connection.sftp = None
        sftp_connection.transport = None
        sftp_connection.connected_at = None

        console.print(f"[bold {NordColors.YELLOW}]Disconnected from SFTP server.[/]")
    except Exception as e:
        console.print(f"[bold {NordColors.RED}]Error during disconnect: {e}[/]")


def check_connection() -> bool:
    """
    Check if there's an active SFTP connection.
    If not, prompt to establish one.
    Returns True if connection is active, False otherwise.
    """
    if sftp_connection.is_connected():
        return True

    console.print(f"[bold {NordColors.RED}]Not connected to any SFTP server.[/]")

    if Confirm.ask(
        f"[bold {NordColors.YELLOW}]Would you like to establish a connection now?[/]",
        default=True,
    ):
        # Ask if they want to select a device or connect manually
        connect_method = Prompt.ask(
            f"[bold {NordColors.PURPLE}]Connection method[/]",
            choices=["device", "manual"],
            default="device",
        )

        if connect_method == "device":
            device = select_device_menu()
            return connect_sftp_device(device)
        else:
            return connect_sftp()

    return False


# ----------------------------------------------------------------
# SFTP File Operations
# ----------------------------------------------------------------
def list_remote_directory() -> None:
    """List the contents of a remote directory."""
    if not check_connection():
        return

    # Create remote path completer for current directory
    remote_completer = RemotePathCompleter(sftp_connection.sftp)

    remote_path = pt_prompt(
        f"[bold {NordColors.PURPLE}]Enter remote directory path: [/]",
        completer=remote_completer,
        default=".",
        history=FileHistory(PATH_HISTORY),
        auto_suggest=AutoSuggestFromHistory(),
    )

    try:
        with Progress(
            SpinnerColumn("dots", style=f"bold {NordColors.FROST_1}"),
            TextColumn("[bold {task.fields[message_color]}]{task.fields[message]}"),
            console=console,
        ) as progress:
            task = progress.add_task(
                "Listing...",
                message=f"Retrieving directory listing for {remote_path}...",
                message_color=NordColors.FROST_2,
            )

            file_list = sftp_connection.sftp.listdir_attr(remote_path)

            progress.update(
                task,
                message=f"Retrieved {len(file_list)} items",
                message_color=NordColors.GREEN,
            )
            time.sleep(0.5)

        # Sort items: directories first, then files
        sorted_items = sorted(
            file_list, key=lambda x: (not (x.st_mode & 0o40000), x.filename.lower())
        )

        table = Table(
            title=f"Contents of {remote_path}",
            show_header=True,
            header_style=f"bold {NordColors.FROST_3}",
            expand=True,
        )

        table.add_column("Type", style="bold", width=4)
        table.add_column("Name", style="bold")
        table.add_column("Size", justify="right")
        table.add_column("Permissions", width=10)
        table.add_column("Modified Time")

        dir_count = 0
        file_count = 0
        total_size = 0

        for item in sorted_items:
            is_dir = item.st_mode & 0o40000  # Check if it's a directory

            # Format size
            if is_dir:
                size_str = "<DIR>"
                dir_count += 1
            else:
                size = item.st_size
                total_size += size

                if size < 1024:
                    size_str = f"{size} B"
                elif size < 1024 * 1024:
                    size_str = f"{size / 1024:.1f} KB"
                elif size < 1024 * 1024 * 1024:
                    size_str = f"{size / (1024 * 1024):.1f} MB"
                else:
                    size_str = f"{size / (1024 * 1024 * 1024):.2f} GB"

                file_count += 1

            # Format modification time
            mod_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(item.st_mtime))

            # Format permissions
            perm = ""
            modes = [
                (0o400, "r"),
                (0o200, "w"),
                (0o100, "x"),
                (0o040, "r"),
                (0o020, "w"),
                (0o010, "x"),
                (0o004, "r"),
                (0o002, "w"),
                (0o001, "x"),
            ]
            for mask, char in modes:
                perm += char if (item.st_mode & mask) else "-"

            # Type indicator
            type_indicator = "📁" if is_dir else "📄"

            table.add_row(
                type_indicator,
                f"[link={remote_path}/{item.filename}]{item.filename}[/]"
                if is_dir
                else item.filename,
                size_str,
                perm,
                mod_time,
            )

        console.print(table)

        # Print summary footer
        console.print(
            f"[{NordColors.FROST_3}]Total: {dir_count} directories, {file_count} files, {total_size / (1024 * 1024):.2f} MB[/]"
        )

    except Exception as e:
        console.print(f"[bold {NordColors.RED}]Failed to list directory: {e}[/]")


def upload_file() -> None:
    """Upload a local file to the remote SFTP server with progress tracking."""
    if not check_connection():
        return

    # Use PathCompleter for local file selection
    path_completer = PathCompleter(only_directories=False, expanduser=True)

    local_path = pt_prompt(
        f"[bold {NordColors.PURPLE}]Enter the local file path to upload: [/]",
        completer=path_completer,
        default=DEFAULT_LOCAL_FOLDER,
        history=FileHistory(PATH_HISTORY),
        auto_suggest=AutoSuggestFromHistory(),
    )

    if not os.path.isfile(local_path):
        console.print(
            f"[bold {NordColors.RED}]Local file does not exist: {local_path}[/]"
        )
        return

    # Create remote path completer
    remote_completer = RemotePathCompleter(sftp_connection.sftp)

    # Suggest the same filename as the local file
    default_remote_name = os.path.basename(local_path)

    remote_path = pt_prompt(
        f"[bold {NordColors.PURPLE}]Enter the remote destination path: [/]",
        completer=remote_completer,
        default=default_remote_name,
        history=FileHistory(PATH_HISTORY),
        auto_suggest=AutoSuggestFromHistory(),
    )

    file_size = os.path.getsize(local_path)

    # Create a progress callback for SFTP
    def progress_callback(transferred, total):
        progress.update(task, completed=transferred)

    try:
        with Progress(
            SpinnerColumn("dots", style=f"bold {NordColors.FROST_2}"),
            TextColumn("[bold {task.fields[message_color]}]{task.fields[message]}"),
            BarColumn(),
            DownloadColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(
                "upload",
                total=file_size,
                message="Uploading...",
                message_color=NordColors.FROST_2,
            )

            sftp_connection.sftp.put(
                local_path, remote_path, callback=progress_callback
            )

        print_success(f"Upload completed: {local_path} → {remote_path}")
    except Exception as e:
        print_error(f"Upload failed: {e}")


def download_file() -> None:
    """Download a remote file from the SFTP server with progress tracking."""
    if not check_connection():
        return

    # Create remote path completer
    remote_completer = RemotePathCompleter(sftp_connection.sftp)

    remote_path = pt_prompt(
        f"[bold {NordColors.PURPLE}]Enter the remote file path to download: [/]",
        completer=remote_completer,
        history=FileHistory(PATH_HISTORY),
        auto_suggest=AutoSuggestFromHistory(),
    )

    # Use PathCompleter for local directory selection
    path_completer = PathCompleter(only_directories=True, expanduser=True)

    local_dest = pt_prompt(
        f"[bold {NordColors.PURPLE}]Enter the local destination directory: [/]",
        completer=path_completer,
        default=DEFAULT_LOCAL_FOLDER,
        history=FileHistory(PATH_HISTORY),
        auto_suggest=AutoSuggestFromHistory(),
    )

    # Ensure the local directory exists
    if not os.path.isdir(local_dest):
        console.print(
            f"[bold {NordColors.RED}]Local directory does not exist: {local_dest}[/]"
        )

        if Confirm.ask(
            f"[bold {NordColors.YELLOW}]Would you like to create this directory?[/]",
            default=True,
        ):
            try:
                os.makedirs(local_dest, exist_ok=True)
                print_success(f"Created directory: {local_dest}")
            except Exception as e:
                print_error(f"Failed to create directory: {e}")
                return
        else:
            return

    try:
        # Get remote file stats
        file_stat = sftp_connection.sftp.stat(remote_path)
        file_size = file_stat.st_size
    except Exception as e:
        console.print(f"[bold {NordColors.RED}]Could not retrieve file size: {e}[/]")
        return

    # Create a progress callback for SFTP
    def progress_callback(transferred, total):
        progress.update(task, completed=transferred)

    try:
        with Progress(
            SpinnerColumn("dots", style=f"bold {NordColors.FROST_2}"),
            TextColumn("[bold {task.fields[message_color]}]{task.fields[message]}"),
            BarColumn(),
            DownloadColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(
                "download",
                total=file_size,
                message="Downloading...",
                message_color=NordColors.FROST_2,
            )

            dest_path = os.path.join(local_dest, os.path.basename(remote_path))
            sftp_connection.sftp.get(remote_path, dest_path, callback=progress_callback)

        print_success(f"Download completed: {remote_path} → {dest_path}")
    except Exception as e:
        print_error(f"Download failed: {e}")


def delete_remote_file() -> None:
    """Delete a remote file from the SFTP server."""
    if not check_connection():
        return

    # Create remote path completer
    remote_completer = RemotePathCompleter(sftp_connection.sftp)

    remote_path = pt_prompt(
        f"[bold {NordColors.PURPLE}]Enter the remote file path to delete: [/]",
        completer=remote_completer,
        history=FileHistory(PATH_HISTORY),
        auto_suggest=AutoSuggestFromHistory(),
    )

    # Check if the item exists and if it's a file or directory
    try:
        stat = sftp_connection.sftp.stat(remote_path)
        is_dir = stat.st_mode & 0o40000
    except Exception:
        print_error(f"Cannot access {remote_path}")
        return

    if is_dir:
        print_warning(
            f"{remote_path} is a directory. Use the delete directory option instead."
        )
        return

    if Confirm.ask(
        f"[bold {NordColors.YELLOW}]Are you sure you want to delete {remote_path}?[/]",
        default=False,
    ):
        try:
            with Progress(
                SpinnerColumn("dots", style=f"bold {NordColors.RED}"),
                TextColumn("[bold {task.fields[message_color]}]{task.fields[message]}"),
                console=console,
            ) as progress:
                task = progress.add_task(
                    "deleting",
                    message=f"Deleting {remote_path}...",
                    message_color=NordColors.RED,
                )

                sftp_connection.sftp.remove(remote_path)

                progress.update(
                    task,
                    message=f"File deleted successfully",
                    message_color=NordColors.GREEN,
                )
                time.sleep(0.5)

            print_success(f"Deleted remote file: {remote_path}")
        except Exception as e:
            print_error(f"Failed to delete file: {e}")


def rename_remote_file() -> None:
    """Rename a remote file on the SFTP server."""
    if not check_connection():
        return

    # Create remote path completer
    remote_completer = RemotePathCompleter(sftp_connection.sftp)

    old_name = pt_prompt(
        f"[bold {NordColors.PURPLE}]Enter the current remote file path: [/]",
        completer=remote_completer,
        history=FileHistory(PATH_HISTORY),
        auto_suggest=AutoSuggestFromHistory(),
    )

    # Check if the file exists
    try:
        sftp_connection.sftp.stat(old_name)
    except Exception:
        print_error(f"Cannot access {old_name}")
        return

    # Get the directory of the old file to set default for new name
    parent_dir = os.path.dirname(old_name)
    file_name = os.path.basename(old_name)

    # Create a completer for the same directory
    same_dir_completer = RemotePathCompleter(
        sftp_connection.sftp, parent_dir if parent_dir else "."
    )

    new_name = pt_prompt(
        f"[bold {NordColors.PURPLE}]Enter the new remote file name/path: [/]",
        completer=same_dir_completer,
        default=file_name,
        history=FileHistory(PATH_HISTORY),
        auto_suggest=AutoSuggestFromHistory(),
    )

    # If new name doesn't include directory, use the same directory
    if "/" not in new_name and parent_dir:
        new_name = f"{parent_dir}/{new_name}"

    try:
        with Progress(
            SpinnerColumn("dots", style=f"bold {NordColors.FROST_2}"),
            TextColumn("[bold {task.fields[message_color]}]{task.fields[message]}"),
            console=console,
        ) as progress:
            task = progress.add_task(
                "renaming",
                message=f"Renaming {old_name} to {new_name}...",
                message_color=NordColors.FROST_2,
            )

            sftp_connection.sftp.rename(old_name, new_name)

            progress.update(
                task,
                message=f"File renamed successfully",
                message_color=NordColors.GREEN,
            )
            time.sleep(0.5)

        print_success(f"Renamed remote file: {old_name} → {new_name}")
    except Exception as e:
        print_error(f"Failed to rename file: {e}")


def create_remote_directory() -> None:
    """Create a new directory on the SFTP server."""
    if not check_connection():
        return

    # Create remote path completer
    remote_completer = RemotePathCompleter(sftp_connection.sftp)

    remote_dir = pt_prompt(
        f"[bold {NordColors.PURPLE}]Enter the remote directory to create: [/]",
        completer=remote_completer,
        history=FileHistory(PATH_HISTORY),
        auto_suggest=AutoSuggestFromHistory(),
    )

    try:
        with Progress(
            SpinnerColumn("dots", style=f"bold {NordColors.FROST_2}"),
            TextColumn("[bold {task.fields[message_color]}]{task.fields[message]}"),
            console=console,
        ) as progress:
            task = progress.add_task(
                "creating",
                message=f"Creating directory {remote_dir}...",
                message_color=NordColors.FROST_2,
            )

            sftp_connection.sftp.mkdir(remote_dir)

            progress.update(
                task,
                message=f"Directory created successfully",
                message_color=NordColors.GREEN,
            )
            time.sleep(0.5)

        print_success(f"Created remote directory: {remote_dir}")
    except Exception as e:
        print_error(f"Failed to create directory: {e}")


def delete_remote_directory() -> None:
    """Delete a directory on the SFTP server."""
    if not check_connection():
        return

    # Create remote path completer
    remote_completer = RemotePathCompleter(sftp_connection.sftp)

    remote_dir = pt_prompt(
        f"[bold {NordColors.PURPLE}]Enter the remote directory to delete: [/]",
        completer=remote_completer,
        history=FileHistory(PATH_HISTORY),
        auto_suggest=AutoSuggestFromHistory(),
    )

    # Check if it's actually a directory
    try:
        stat = sftp_connection.sftp.stat(remote_dir)
        is_dir = stat.st_mode & 0o40000
        if not is_dir:
            print_error(f"{remote_dir} is not a directory.")
            return
    except Exception as e:
        print_error(f"Cannot access {remote_dir}: {e}")
        return

    # Check if directory is empty
    try:
        contents = sftp_connection.sftp.listdir(remote_dir)
        if contents:
            print_warning(f"Directory is not empty. Contains {len(contents)} items.")

            if not Confirm.ask(
                f"[bold {NordColors.RED}]Force delete non-empty directory?[/]",
                default=False,
            ):
                return

            # Recursive delete - dangerous!
            if Confirm.ask(
                f"[bold {NordColors.RED}]WARNING: This will delete ALL contents. Proceed?[/]",
                default=False,
            ):
                # Implementing simple recursive delete
                def rm_rf(path):
                    files = sftp_connection.sftp.listdir(path)
                    for f in files:
                        filepath = os.path.join(path, f)
                        try:
                            # Check if it's a directory
                            try:
                                sftp_connection.sftp.listdir(filepath)
                                rm_rf(filepath)
                            except:
                                # Not a directory, remove the file
                                sftp_connection.sftp.remove(filepath)
                                print_step(f"Deleted file: {filepath}")
                        except Exception as e:
                            print_error(f"Failed to remove {filepath}: {e}")
                            return False
                    # Now remove the directory
                    sftp_connection.sftp.rmdir(path)
                    return True

                with Progress(
                    SpinnerColumn("dots", style=f"bold {NordColors.RED}"),
                    TextColumn(
                        "[bold {task.fields[message_color]}]{task.fields[message]}"
                    ),
                    console=console,
                ) as progress:
                    task = progress.add_task(
                        "deleting",
                        message=f"Recursively deleting {remote_dir}...",
                        message_color=NordColors.RED,
                    )

                    success = rm_rf(remote_dir)

                    if success:
                        progress.update(
                            task,
                            message=f"Directory and all contents deleted",
                            message_color=NordColors.GREEN,
                        )
                        print_success(
                            f"Recursively deleted remote directory: {remote_dir}"
                        )
                    else:
                        progress.update(
                            task,
                            message=f"Failed to delete all contents",
                            message_color=NordColors.RED,
                        )
                        print_error(
                            f"Failed to recursively delete directory: {remote_dir}"
                        )

                return
            else:
                return
    except Exception as e:
        print_error(f"Failed to check directory contents: {e}")
        return

    # Regular delete for empty directory
    if Confirm.ask(
        f"[bold {NordColors.YELLOW}]Are you sure you want to delete this directory?[/]",
        default=False,
    ):
        try:
            with Progress(
                SpinnerColumn("dots", style=f"bold {NordColors.RED}"),
                TextColumn("[bold {task.fields[message_color]}]{task.fields[message]}"),
                console=console,
            ) as progress:
                task = progress.add_task(
                    "deleting",
                    message=f"Deleting directory {remote_dir}...",
                    message_color=NordColors.RED,
                )

                sftp_connection.sftp.rmdir(remote_dir)

                progress.update(
                    task,
                    message=f"Directory deleted successfully",
                    message_color=NordColors.GREEN,
                )
                time.sleep(0.5)

            print_success(f"Deleted remote directory: {remote_dir}")
        except Exception as e:
            print_error(f"Failed to delete directory: {e}")


# ----------------------------------------------------------------
# Main Menu and Program Control
# ----------------------------------------------------------------
def display_status_bar() -> None:
    """Display a status bar with connection information."""
    connection_status = sftp_connection.get_connection_info()

    status_color = (
        NordColors.GREEN if sftp_connection.is_connected() else NordColors.RED
    )
    status_text = "CONNECTED" if sftp_connection.is_connected() else "DISCONNECTED"

    console.print(
        Panel(
            Text.from_markup(
                f"[bold {status_color}]Status: {status_text}[/] | [dim]{connection_status}[/]"
            ),
            border_style=NordColors.FROST_4,
            padding=(0, 2),
        )
    )


def main_menu() -> None:
    """
    Display the interactive SFTP Toolkit menu and loop until exit.
    """
    menu_options = [
        ("1", "Connect to SFTP Server (manual)"),
        ("2", "Connect to SFTP Server (select device)"),
        ("3", "List Remote Directory"),
        ("4", "Upload File"),
        ("5", "Download File"),
        ("6", "Rename Remote File"),
        ("7", "Create Remote Directory"),
        ("8", "Delete Remote File"),
        ("9", "Delete Remote Directory"),
        ("A", "Disconnect from SFTP Server"),
        ("H", "Show Help"),
        ("0", "Exit"),
    ]

    while True:
        console.clear()
        console.print(create_header())
        display_status_bar()

        # Current time display
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        console.print(
            Align.center(
                f"[{NordColors.SNOW_STORM_1}]Current Time: {current_time}[/] | [{NordColors.SNOW_STORM_1}]Host: {HOSTNAME}[/]"
            )
        )
        console.print()

        console.print(f"[bold {NordColors.PURPLE}]SFTP Toolkit Menu[/]")

        # Build menu table
        table = Table(
            show_header=True, header_style=f"bold {NordColors.FROST_3}", expand=True
        )

        table.add_column("Option", style="bold", width=8)
        table.add_column("Description", style="bold")

        # Add menu options with highlighting for connected/disconnected state
        for option, description in menu_options:
            if (
                option in ["3", "4", "5", "6", "7", "8", "9"]
                and not sftp_connection.is_connected()
            ):
                # Dim options that require connection
                table.add_row(option, f"[dim]{description} (requires connection)[/dim]")
            elif option == "A" and not sftp_connection.is_connected():
                # Dim disconnect option when not connected
                table.add_row(option, f"[dim]{description} (not connected)[/dim]")
            else:
                table.add_row(option, description)

        console.print(table)

        # Command input with history and auto-completion
        command_history = FileHistory(COMMAND_HISTORY)

        choice = pt_prompt(
            f"[bold {NordColors.PURPLE}]Enter your choice: [/]",
            history=command_history,
            auto_suggest=AutoSuggestFromHistory(),
        ).upper()

        if choice == "1":
            connect_sftp()
            pt_prompt(f"[bold {NordColors.FROST_2}]Press Enter to continue[/]")

        elif choice == "2":
            device = select_device_menu()
            connect_sftp_device(device)
            pt_prompt(f"[bold {NordColors.FROST_2}]Press Enter to continue[/]")

        elif choice == "3":
            list_remote_directory()
            pt_prompt(f"[bold {NordColors.FROST_2}]Press Enter to continue[/]")

        elif choice == "4":
            upload_file()
            pt_prompt(f"[bold {NordColors.FROST_2}]Press Enter to continue[/]")

        elif choice == "5":
            download_file()
            pt_prompt(f"[bold {NordColors.FROST_2}]Press Enter to continue[/]")

        elif choice == "6":
            rename_remote_file()
            pt_prompt(f"[bold {NordColors.FROST_2}]Press Enter to continue[/]")

        elif choice == "7":
            create_remote_directory()
            pt_prompt(f"[bold {NordColors.FROST_2}]Press Enter to continue[/]")

        elif choice == "8":
            delete_remote_file()
            pt_prompt(f"[bold {NordColors.FROST_2}]Press Enter to continue[/]")

        elif choice == "9":
            delete_remote_directory()
            pt_prompt(f"[bold {NordColors.FROST_2}]Press Enter to continue[/]")

        elif choice == "A":
            disconnect_sftp()
            pt_prompt(f"[bold {NordColors.FROST_2}]Press Enter to continue[/]")

        elif choice == "H":
            show_help()
            pt_prompt(f"[bold {NordColors.FROST_2}]Press Enter to continue[/]")

        elif choice == "0":
            if sftp_connection.is_connected():
                disconnect_sftp()

            console.print()
            console.print(
                Panel(
                    Text(
                        f"Thank you for using SFTP Toolkit!",
                        style=f"bold {NordColors.FROST_2}",
                    ),
                    border_style=Style(color=NordColors.FROST_1),
                    padding=(1, 2),
                )
            )
            sys.exit(0)

        else:
            print_error(f"Invalid selection: {choice}")
            pt_prompt(f"[bold {NordColors.FROST_2}]Press Enter to continue[/]")


# ----------------------------------------------------------------
# Main Entry Point
# ----------------------------------------------------------------
def main() -> None:
    """
    Main function: load environment variables, clear the console,
    and launch the interactive menu.
    """
    # Load environment variables
    load_env()

    # Clear screen and show banner
    console.clear()

    # Main menu loop
    main_menu()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_warning("Operation cancelled by user")
        # Clean up connections
        if sftp_connection.is_connected():
            disconnect_sftp()
        sys.exit(0)
    except Exception as e:
        console.print_exception()
        print_error(f"An unexpected error occurred: {e}")
        sys.exit(1)
