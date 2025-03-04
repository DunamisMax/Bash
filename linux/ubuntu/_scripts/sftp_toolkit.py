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

Version: 1.1.0
"""

# ----------------------------------------------------------------
# Imports and Dependency Checks
# ----------------------------------------------------------------
import os
import sys
import time
import socket
import getpass
from dataclasses import dataclass
from typing import List

import paramiko
import pyfiglet
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TimeRemainingColumn,
    DownloadColumn,
)

# Import prompt_toolkit for robust auto-completion
try:
    from prompt_toolkit import prompt as pt_prompt
    from prompt_toolkit.completion import PathCompleter, Completer, Completion
except ImportError:
    pt_prompt = None


# ----------------------------------------------------------------
# Nord-Themed Colors and Global Constants
# ----------------------------------------------------------------
class NordColors:
    POLAR_NIGHT_1 = "#2E3440"
    POLAR_NIGHT_2 = "#3B4252"
    POLAR_NIGHT_3 = "#434C5E"
    POLAR_NIGHT_4 = "#4C566A"
    SNOW_STORM_1 = "#D8DEE9"
    SNOW_STORM_2 = "#E5E9F0"
    SNOW_STORM_3 = "#ECEFF4"
    FROST_1 = "#8FBCBB"
    FROST_2 = "#88C0D0"
    FROST_3 = "#81A1C1"
    FROST_4 = "#5E81AC"
    RED = "#BF616A"
    ORANGE = "#D08770"
    YELLOW = "#EBCB8B"
    GREEN = "#A3BE8C"
    PURPLE = "#B48EAD"


console = Console()

# Global SFTP connection objects
sftp = None
transport = None

# Default local folder for all file operations
DEFAULT_LOCAL_FOLDER = "/home/sawyer/Downloads"


# ----------------------------------------------------------------
# Helper: Unified Input Function with prompt_toolkit Integration
# ----------------------------------------------------------------
def get_input(message: str, completer=None, default: str = "") -> str:
    """
    Return user input using prompt_toolkit if available (with auto-completion)
    or fallback to standard input.
    """
    if pt_prompt:
        return pt_prompt(message, completer=completer, default=default)
    else:
        # Fallback if prompt_toolkit is not installed
        return input(message)


# ----------------------------------------------------------------
# Custom Remote Path Completer
# ----------------------------------------------------------------
if pt_prompt:

    class RemotePathCompleter(Completer):
        """
        Completer for remote file paths using the active SFTP client.
        This completer lists files in the current remote base directory.
        """

        def __init__(self, sftp_client, base_path="."):
            self.sftp = sftp_client
            self.base_path = base_path

        def get_completions(self, document, complete_event):
            text = document.text
            try:
                files = self.sftp.listdir(self.base_path)
            except Exception:
                files = []
            for f in files:
                if f.startswith(text):
                    yield Completion(f, start_position=-len(text))


# ----------------------------------------------------------------
# Environment Loader and SSH Key Helper Functions
# ----------------------------------------------------------------
def load_env() -> None:
    """
    Load environment variables from a ".env" file.
    Expected format: SSH_KEY_PASSWORD="your_key_password"
    """
    try:
        with open(".env", "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip().strip('"').strip("'")
    except Exception as e:
        console.print(f"[bold {NordColors.RED}]Error loading .env file: {e}[/]")


def get_default_username() -> str:
    """
    Return the default username. If run with sudo, use the original user's username.
    """
    return os.getenv("SUDO_USER") or getpass.getuser()


def load_private_key():
    """
    Load the default SSH private key from ~/.ssh/id_rsa.
    If the key is encrypted, use SSH_KEY_PASSWORD from environment.
    """
    key_path = os.path.expanduser("~/.ssh/id_rsa")
    try:
        key = paramiko.RSAKey.from_private_key_file(key_path)
        return key
    except paramiko.PasswordRequiredException:
        key_password = os.getenv("SSH_KEY_PASSWORD")
        if not key_password:
            console.print(
                f"[bold {NordColors.RED}]SSH key password not found in .env.[/]"
            )
            return None
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
# Device Data Structures and Loader Functions
# ----------------------------------------------------------------
@dataclass
class Device:
    name: str
    ip_address: str
    description: str


def load_tailscale_devices() -> List[Device]:
    """Load predefined Tailscale devices."""
    return [
        Device("ubuntu-server", "100.109.43.88", "Primary Ubuntu Server"),
        Device("ubuntu-lenovo", "100.66.213.7", "Development Laptop"),
        Device("raspberrypi-5", "100.105.117.18", "Raspberry Pi 5"),
        Device("raspberrypi-3", "100.116.191.42", "Raspberry Pi 3"),
        Device("ubuntu-server-vm-01", "100.84.119.114", "Ubuntu VM 1"),
        Device("ubuntu-server-vm-02", "100.122.237.56", "Ubuntu VM 2"),
        Device("ubuntu-server-vm-03", "100.97.229.120", "Ubuntu VM 3"),
        Device("ubuntu-server-vm-04", "100.73.171.7", "Ubuntu VM 4"),
        Device("ubuntu-lenovo-vm-01", "100.107.79.81", "Lenovo VM 1"),
        Device("ubuntu-lenovo-vm-02", "100.78.101.2", "Lenovo VM 2"),
        Device("ubuntu-lenovo-vm-03", "100.95.115.62", "Lenovo VM 3"),
        Device("ubuntu-lenovo-vm-04", "100.92.31.94", "Lenovo VM 4"),
    ]


def load_local_devices() -> List[Device]:
    """Load predefined local network devices."""
    return [
        Device("ubuntu-server", "192.168.0.73", "Primary Server (LAN)"),
        Device("ubuntu-lenovo", "192.168.0.31", "Development Laptop (LAN)"),
        Device("raspberrypi-5", "192.168.0.40", "Raspberry Pi 5 (LAN)"),
        Device("raspberrypi-3", "192.168.0.100", "Raspberry Pi 3 (LAN)"),
    ]


def select_device_menu() -> Device:
    """
    Display a device selection menu for choosing Tailscale or local devices.
    Ensures proper integer conversion for the selection.
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
        table.add_row(str(idx), device.name, device.ip_address, device.description)
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
# SFTP Connection and Operations
# ----------------------------------------------------------------
class AppConfig:
    """Application configuration constants."""

    SFTP_DEFAULT_PORT = 22


def connect_sftp() -> None:
    """
    Establish an SFTP connection using key-based authentication.
    Prompts for hostname, port, and username.
    """
    global sftp, transport
    console.print(
        Panel(f"[bold {NordColors.FROST_2}]SFTP Connection Setup[/]", expand=False)
    )
    hostname = Prompt.ask(f"[bold {NordColors.PURPLE}]Enter SFTP Hostname[/]")
    port = IntPrompt.ask(
        f"[bold {NordColors.PURPLE}]Enter Port[/]", default=AppConfig.SFTP_DEFAULT_PORT
    )
    username = Prompt.ask(
        f"[bold {NordColors.PURPLE}]Enter Username[/]", default=get_default_username()
    )

    key = load_private_key()
    if key is None:
        console.print(
            f"[bold {NordColors.RED}]Could not load SSH private key. Connection aborted.[/]"
        )
        return

    try:
        transport = paramiko.Transport((hostname, port))
        transport.connect(username=username, pkey=key)
        sftp = paramiko.SFTPClient.from_transport(transport)
        console.print(
            f"[bold {NordColors.GREEN}]Successfully connected to SFTP server using key-based authentication.[/]"
        )
    except Exception as e:
        console.print(f"[bold {NordColors.RED}]Error connecting to SFTP server: {e}[/]")
        sftp = None
        transport = None


def connect_sftp_device(device: Device) -> None:
    """
    Establish an SFTP connection using a predefined device.
    The device's IP address is used as the hostname.
    """
    global sftp, transport
    console.print(
        Panel(
            f"[bold {NordColors.FROST_2}]Connecting to {device.name} ({device.ip_address})[/]",
            expand=False,
        )
    )
    port = IntPrompt.ask(
        f"[bold {NordColors.PURPLE}]Enter Port[/]", default=AppConfig.SFTP_DEFAULT_PORT
    )
    username = Prompt.ask(
        f"[bold {NordColors.PURPLE}]Enter Username[/]", default=get_default_username()
    )

    key = load_private_key()
    if key is None:
        console.print(
            f"[bold {NordColors.RED}]Could not load SSH private key. Connection aborted.[/]"
        )
        return

    try:
        transport = paramiko.Transport((device.ip_address, port))
        transport.connect(username=username, pkey=key)
        sftp = paramiko.SFTPClient.from_transport(transport)
        console.print(
            f"[bold {NordColors.GREEN}]Successfully connected to {device.name} using key-based authentication.[/]"
        )
    except Exception as e:
        console.print(
            f"[bold {NordColors.RED}]Error connecting to {device.name}: {e}[/]"
        )
        sftp = None
        transport = None


def disconnect_sftp() -> None:
    """Disconnect from the SFTP server and close connections."""
    global sftp, transport
    if sftp:
        sftp.close()
        sftp = None
    if transport:
        transport.close()
        transport = None
    console.print(f"[bold {NordColors.YELLOW}]Disconnected from SFTP server.[/]")


def list_remote_directory() -> None:
    """List the contents of a remote directory."""
    if not sftp:
        console.print(f"[bold {NordColors.RED}]Not connected. Please connect first.[/]")
        return

    remote_path = Prompt.ask(
        f"[bold {NordColors.PURPLE}]Enter remote directory path[/]", default="."
    )
    try:
        file_list = sftp.listdir_attr(remote_path)
        table = Table(
            title=f"Contents of {remote_path}",
            show_header=True,
            header_style=f"bold {NordColors.FROST_3}",
        )
        table.add_column("Name", style="bold")
        table.add_column("Size", justify="right")
        table.add_column("Modified Time")
        for item in file_list:
            mod_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(item.st_mtime))
            table.add_row(item.filename, f"{item.st_size} bytes", mod_time)
        console.print(table)
    except Exception as e:
        console.print(f"[bold {NordColors.RED}]Failed to list directory: {e}[/]")


def upload_file() -> None:
    """Upload a local file to the remote SFTP server with progress tracking."""
    if not sftp:
        console.print(f"[bold {NordColors.RED}]Not connected. Please connect first.[/]")
        return

    # Use prompt_toolkit PathCompleter for local file selection.
    local_completer = PathCompleter(only_files=True, expanduser=True)
    local_path = get_input(
        "Enter the local file path to upload: ",
        completer=local_completer,
        default=DEFAULT_LOCAL_FOLDER,
    )
    if not os.path.isfile(local_path):
        console.print(f"[bold {NordColors.RED}]Local file does not exist.[/]")
        return

    remote_path = Prompt.ask(
        f"[bold {NordColors.PURPLE}]Enter the remote destination path[/]"
    )
    file_size = os.path.getsize(local_path)

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
            task = progress.add_task("upload", total=file_size, message="Uploading...")
            sftp.put(local_path, remote_path, callback=progress_callback)
        console.print(
            f"[bold {NordColors.GREEN}]Upload completed: {local_path} -> {remote_path}[/]"
        )
    except Exception as e:
        console.print(f"[bold {NordColors.RED}]Upload failed: {e}[/]")


def download_file() -> None:
    """Download a remote file from the SFTP server with progress tracking."""
    if not sftp:
        console.print(f"[bold {NordColors.RED}]Not connected. Please connect first.[/]")
        return

    # Use prompt_toolkit auto-completion for remote file path if available.
    if pt_prompt:
        remote_completer = RemotePathCompleter(sftp)
        remote_path = get_input(
            "Enter the remote file path to download: ",
            completer=remote_completer,
            default="",
        )
    else:
        remote_path = Prompt.ask(
            f"[bold {NordColors.PURPLE}]Enter the remote file path to download[/]"
        )

    # For local destination directory, use prompt_toolkit PathCompleter for directories.
    local_dir_completer = PathCompleter(only_directories=True, expanduser=True)
    local_dest = get_input(
        "Enter the local destination directory: ",
        completer=local_dir_completer,
        default=DEFAULT_LOCAL_FOLDER,
    )

    try:
        file_size = sftp.stat(remote_path).st_size
    except Exception as e:
        console.print(f"[bold {NordColors.RED}]Could not retrieve file size: {e}[/]")
        return

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
                "download", total=file_size, message="Downloading..."
            )
            dest_path = os.path.join(local_dest, os.path.basename(remote_path))
            sftp.get(remote_path, dest_path, callback=progress_callback)
        console.print(
            f"[bold {NordColors.GREEN}]Download completed: {remote_path} -> {local_dest}[/]"
        )
    except Exception as e:
        console.print(f"[bold {NordColors.RED}]Download failed: {e}[/]")


def delete_remote_file() -> None:
    """Delete a remote file from the SFTP server."""
    if not sftp:
        console.print(f"[bold {NordColors.RED}]Not connected. Please connect first.[/]")
        return

    remote_path = Prompt.ask(
        f"[bold {NordColors.PURPLE}]Enter the remote file path to delete[/]"
    )
    if Confirm.ask(
        f"[bold {NordColors.YELLOW}]Are you sure you want to delete this file?[/]",
        default=False,
    ):
        try:
            sftp.remove(remote_path)
            console.print(
                f"[bold {NordColors.GREEN}]Deleted remote file: {remote_path}[/]"
            )
        except Exception as e:
            console.print(f"[bold {NordColors.RED}]Failed to delete file: {e}[/]")


def rename_remote_file() -> None:
    """Rename a remote file on the SFTP server."""
    if not sftp:
        console.print(f"[bold {NordColors.RED}]Not connected. Please connect first.[/]")
        return

    old_name = Prompt.ask(
        f"[bold {NordColors.PURPLE}]Enter the current remote file path[/]"
    )
    new_name = Prompt.ask(
        f"[bold {NordColors.PURPLE}]Enter the new remote file name/path[/]"
    )
    try:
        sftp.rename(old_name, new_name)
        console.print(f"[bold {NordColors.GREEN}]Renamed remote file to: {new_name}[/]")
    except Exception as e:
        console.print(f"[bold {NordColors.RED}]Failed to rename file: {e}[/]")


def create_remote_directory() -> None:
    """Create a new directory on the SFTP server."""
    if not sftp:
        console.print(f"[bold {NordColors.RED}]Not connected. Please connect first.[/]")
        return

    remote_dir = Prompt.ask(
        f"[bold {NordColors.PURPLE}]Enter the remote directory to create[/]"
    )
    try:
        sftp.mkdir(remote_dir)
        console.print(
            f"[bold {NordColors.GREEN}]Created remote directory: {remote_dir}[/]"
        )
    except Exception as e:
        console.print(f"[bold {NordColors.RED}]Failed to create directory: {e}[/]")


def delete_remote_directory() -> None:
    """Delete a directory on the SFTP server."""
    if not sftp:
        console.print(f"[bold {NordColors.RED}]Not connected. Please connect first.[/]")
        return

    remote_dir = Prompt.ask(
        f"[bold {NordColors.PURPLE}]Enter the remote directory to delete[/]"
    )
    if Confirm.ask(
        f"[bold {NordColors.YELLOW}]Are you sure you want to delete this directory?[/]",
        default=False,
    ):
        try:
            sftp.rmdir(remote_dir)
            console.print(
                f"[bold {NordColors.GREEN}]Deleted remote directory: {remote_dir}[/]"
            )
        except Exception as e:
            console.print(f"[bold {NordColors.RED}]Failed to delete directory: {e}[/]")


# ----------------------------------------------------------------
# UI Components and Main Menu
# ----------------------------------------------------------------
def display_banner() -> None:
    """
    Display a dynamic ASCII art banner using Pyfiglet with Nord-themed styling.
    """
    fonts = ["slant", "big", "digital"]
    ascii_banner = ""
    for font in fonts:
        try:
            fig = pyfiglet.Figlet(font=font)
            ascii_banner = fig.renderText("SFTP Toolkit")
            if ascii_banner.strip():
                break
        except Exception:
            continue
    banner_panel = Panel(
        ascii_banner,
        style=f"bold {NordColors.FROST_2}",
        border_style=NordColors.FROST_3,
    )
    console.print(banner_panel)


def main_menu() -> None:
    """
    Display the interactive SFTP Toolkit menu and loop until exit.
    Defaults to device selection for quick connection.
    """
    while True:
        console.print(f"\n[bold {NordColors.PURPLE}]SFTP Toolkit Menu[/]")
        table = Table(show_header=True, header_style=f"bold {NordColors.FROST_3}")
        table.add_column("Option", style="bold", width=4)
        table.add_column("Description", style="bold")
        table.add_row("1", "Connect to SFTP Server (manual)")
        table.add_row("2", "Connect to SFTP Server (select device)")
        table.add_row("3", "List Remote Directory")
        table.add_row("4", "Upload File")
        table.add_row("5", "Download File")
        table.add_row("6", "Rename Remote File")
        table.add_row("7", "Create Remote Directory")
        table.add_row("8", "Delete Remote Directory")
        table.add_row("9", "Delete Remote File")
        table.add_row("A", "Disconnect from SFTP Server")
        table.add_row("0", "Exit")
        console.print(table)

        choice = Prompt.ask(
            f"[bold {NordColors.PURPLE}]Enter your choice[/]",
            choices=[str(i) for i in list(range(1, 10))] + ["A", "0"],
            default="2",
        )

        if choice == "1":
            connect_sftp()
        elif choice == "2":
            device = select_device_menu()
            connect_sftp_device(device)
        elif choice == "3":
            list_remote_directory()
        elif choice == "4":
            upload_file()
        elif choice == "5":
            download_file()
        elif choice == "6":
            rename_remote_file()
        elif choice == "7":
            create_remote_directory()
        elif choice == "8":
            delete_remote_directory()
        elif choice == "9":
            delete_remote_file()
        elif choice.upper() == "A":
            disconnect_sftp()
        elif choice == "0":
            if sftp:
                disconnect_sftp()
            console.print(
                f"[bold {NordColors.YELLOW}]Exiting SFTP Toolkit. Goodbye![/]"
            )
            sys.exit(0)
        else:
            console.print(
                f"[bold {NordColors.RED}]Invalid selection, please try again.[/]"
            )
        time.sleep(1)


# ----------------------------------------------------------------
# Main Entry Point
# ----------------------------------------------------------------
def main() -> None:
    """
    Main function: load environment variables, clear the console,
    display the banner, and launch the interactive menu.
    """
    load_env()
    console.clear()
    display_banner()
    main_menu()


if __name__ == "__main__":
    main()
