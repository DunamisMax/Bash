#!/usr/bin/env python3
"""
Enhanced Python Development Environment Setup Tool
-------------------------------------------------

A beautiful, interactive terminal-based utility for setting up a Python development
environment on Ubuntu/Linux systems. This tool provides options to:
  • Perform system checks and install system-level dependencies
  • Install pyenv and the latest version of Python
  • Install pipx (if missing) and use it to install recommended Python tools
  • Install common development tools via pip

All functionality is menu-driven with an attractive Nord-themed interface.

Note: This script runs as non-root but will invoke sudo for operations that require
root privileges.

Version: 3.0.0
"""

import atexit
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Tuple, Set, Callable

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.prompt import Prompt, Confirm
    from rich.progress import (
        Progress,
        SpinnerColumn,
        BarColumn,
        TextColumn,
        TimeRemainingColumn,
        TaskID,
    )
    from rich.live import Live
    from rich.layout import Layout
    from rich.status import Status
    from rich import box
    import pyfiglet
except ImportError:
    # If Rich is not installed, install it first
    print("Installing required dependencies...")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "rich", "pyfiglet"], check=True
    )

    # Then import again
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.prompt import Prompt, Confirm
    from rich.progress import (
        Progress,
        SpinnerColumn,
        BarColumn,
        TextColumn,
        TimeRemainingColumn,
        TaskID,
    )
    from rich.live import Live
    from rich.layout import Layout
    from rich.status import Status
    from rich import box
    import pyfiglet

# ==============================
# Configuration & Constants
# ==============================
APP_NAME = "Python Dev Setup"
VERSION = "3.0.0"
HOME_DIR = os.path.expanduser("~")
PYENV_DIR = os.path.join(HOME_DIR, ".pyenv")
PYENV_BIN = os.path.join(PYENV_DIR, "bin", "pyenv")

# Terminal dimensions
TERM_WIDTH = min(shutil.get_terminal_size().columns, 100)

# System packages
SYSTEM_DEPENDENCIES = [
    "build-essential",
    "libssl-dev",
    "zlib1g-dev",
    "libbz2-dev",
    "libreadline-dev",
    "libsqlite3-dev",
    "libncurses5-dev",
    "libncursesw5-dev",
    "xz-utils",
    "tk-dev",
    "libffi-dev",
    "liblzma-dev",
    "python3-dev",
    "git",
    "curl",
    "wget",
]

# Top Python tools to install
TOP_PYTHON_TOOLS = [
    "rich",
    "pyfiglet",
    "black",
    "isort",
    "flake8",
    "mypy",
    "pytest",
    "pre-commit",
    "ipython",
    "cookiecutter",
    "pylint",
    "sphinx",
    "twine",
    "autopep8",
    "bandit",
    "poetry",
    "pydocstyle",
    "yapf",
    "httpie",
]

# Tools to install via pipx
PIPX_TOOLS = TOP_PYTHON_TOOLS

# ==============================
# Nord-Themed Console Setup
# ==============================
console = Console()


# Nord Theme Color Definitions
class NordColors:
    """Nord theme color palette for consistent UI styling."""

    # Polar Night (dark/background)
    NORD0 = "#2E3440"
    NORD1 = "#3B4252"
    NORD2 = "#434C5E"
    NORD3 = "#4C566A"

    # Snow Storm (light/text)
    NORD4 = "#D8DEE9"
    NORD5 = "#E5E9F0"
    NORD6 = "#ECEFF4"

    # Frost (blue accents)
    NORD7 = "#8FBCBB"
    NORD8 = "#88C0D0"
    NORD9 = "#81A1C1"
    NORD10 = "#5E81AC"

    # Aurora (status indicators)
    NORD11 = "#BF616A"  # Red (errors)
    NORD12 = "#D08770"  # Orange (warnings)
    NORD13 = "#EBCB8B"  # Yellow (caution)
    NORD14 = "#A3BE8C"  # Green (success)
    NORD15 = "#B48EAD"  # Purple (special)


# ==============================
# UI Helper Functions
# ==============================
def print_header(text: str) -> None:
    """Print a striking header using pyfiglet."""
    ascii_art = pyfiglet.figlet_format(text, font="slant")
    console.print(
        Panel(
            ascii_art,
            style=f"bold {NordColors.NORD8}",
            border_style=f"bold {NordColors.NORD9}",
            expand=False,
        )
    )


def print_section(title: str) -> None:
    """Print a formatted section header."""
    console.print(
        Panel(
            title,
            style=f"bold {NordColors.NORD8}",
            border_style=f"bold {NordColors.NORD9}",
            expand=True,
        )
    )


def print_info(message: str) -> None:
    """Print an informational message."""
    console.print(f"[{NordColors.NORD9}]{message}[/]")


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[bold {NordColors.NORD14}]✓ {message}[/]")


def print_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"[bold {NordColors.NORD13}]⚠ {message}[/]")


def print_error(message: str) -> None:
    """Print an error message."""
    console.print(f"[bold {NordColors.NORD11}]✗ {message}[/]")


def print_step(text: str) -> None:
    """Print a step description."""
    console.print(f"[{NordColors.NORD8}]• {text}[/]")


def clear_screen() -> None:
    """Clear the terminal screen."""
    console.clear()


def pause() -> None:
    """Pause execution until user presses Enter."""
    console.input(f"\n[{NordColors.NORD15}]Press Enter to continue...[/]")


def get_user_input(prompt: str, default: str = "") -> str:
    """Get input from the user with a styled prompt."""
    return Prompt.ask(f"[bold {NordColors.NORD15}]{prompt}[/]", default=default)


def get_user_choice(prompt: str, choices: List[str]) -> str:
    """Get a choice from the user with a styled prompt."""
    return Prompt.ask(
        f"[bold {NordColors.NORD15}]{prompt}[/]", choices=choices, show_choices=True
    )


def get_user_confirmation(prompt: str) -> bool:
    """Get confirmation from the user."""
    return Confirm.ask(f"[bold {NordColors.NORD15}]{prompt}[/]")


def create_menu_table(title: str, options: List[Tuple[str, str]]) -> Table:
    """Create a Rich table for menu options."""
    table = Table(
        title=title,
        box=box.ROUNDED,
        title_style=f"bold {NordColors.NORD8}",
        expand=True,
    )
    table.add_column("Option", style=f"{NordColors.NORD9}", justify="center", width=8)
    table.add_column("Description", style=f"{NordColors.NORD4}")

    for key, description in options:
        table.add_row(key, description)

    return table


# ==============================
# Signal Handling & Cleanup
# ==============================
def cleanup() -> None:
    """Perform cleanup tasks before exit."""
    with Status(f"[{NordColors.NORD8}]Performing cleanup tasks...[/]"):
        time.sleep(0.5)  # Give a visual indication of cleanup


atexit.register(cleanup)


def signal_handler(signum, frame) -> None:
    """Handle termination signals gracefully."""
    sig_name = (
        signal.Signals(signum).name
        if hasattr(signal, "Signals")
        else f"signal {signum}"
    )
    print_warning(f"\nScript interrupted by {sig_name}.")
    cleanup()
    sys.exit(128 + signum)


# Register signal handlers
for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
    signal.signal(sig, signal_handler)


# ==============================
# System Helper Functions
# ==============================
def run_command(
    cmd: List[str],
    shell: bool = False,
    check: bool = True,
    capture_output: bool = True,
    timeout: int = 300,  # Extended timeout for longer operations
    verbose: bool = False,
    sudo: bool = False,
) -> subprocess.CompletedProcess:
    """Run a shell command and handle errors."""
    if sudo and os.geteuid() != 0:
        cmd = ["sudo"] + cmd

    if verbose:
        if shell:
            print_step(f"Executing: {cmd}")
        else:
            print_step(f"Executing: {' '.join(cmd)}")

    try:
        with Status(
            f"[{NordColors.NORD8}]Running command: {' '.join(cmd) if not shell else cmd}[/]"
        ):
            return subprocess.run(
                cmd,
                shell=shell,
                check=check,
                text=True,
                capture_output=capture_output,
                timeout=timeout,
            )
    except subprocess.CalledProcessError as e:
        if shell:
            print_error(f"Command failed: {cmd}")
        else:
            print_error(f"Command failed: {' '.join(cmd)}")

        if hasattr(e, "stdout") and e.stdout:
            console.print(f"[dim]Stdout: {e.stdout.strip()}[/dim]")
        if hasattr(e, "stderr") and e.stderr:
            console.print(
                Panel(
                    e.stderr.strip(),
                    title="Error Output",
                    border_style=f"bold {NordColors.NORD11}",
                )
            )
        raise
    except subprocess.TimeoutExpired:
        print_error(f"Command timed out after {timeout} seconds")
        raise


def is_root() -> bool:
    """Check if script is running with elevated privileges."""
    return os.geteuid() == 0


def check_command_available(command: str) -> bool:
    """Check if a command is available in PATH."""
    return shutil.which(command) is not None


# ==============================
# Core Functions
# ==============================
def check_system() -> bool:
    """Check system compatibility and required tools."""
    print_section("Checking System Compatibility")

    os_name = platform.system().lower()
    if os_name != "linux":
        print_warning(f"This script is designed for Linux, not {os_name}.")
        if not get_user_confirmation("Continue anyway?"):
            return False

    # Create a table for system information
    table = Table(title="System Information", box=box.ROUNDED)
    table.add_column("Component", style=f"bold {NordColors.NORD9}")
    table.add_column("Value", style=f"{NordColors.NORD4}")

    table.add_row("Python Version", platform.python_version())
    table.add_row("Operating System", platform.platform())
    table.add_row("User", os.environ.get("USER", "Unknown"))
    table.add_row("Home Directory", HOME_DIR)
    console.print(table)

    required_tools = ["git", "curl", "gcc"]
    missing = [tool for tool in required_tools if shutil.which(tool) is None]

    if missing:
        print_error(
            f"Missing required tools: {', '.join(missing)}. These will be installed."
        )
    else:
        print_success("All basic required tools are present.")

    print_success("System check completed.")
    return True


def install_system_dependencies() -> bool:
    """Install system-level dependencies using apt-get."""
    print_section("Installing System Dependencies")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        expand=True,
    ) as progress:
        try:
            # Update package lists
            task = progress.add_task("[bold green]Updating package lists...", total=1)
            try:
                run_command(["apt-get", "update"], sudo=True)
                progress.update(task, advance=1)
                print_success("Package lists updated.")
            except Exception as e:
                print_error(f"Failed to update package lists: {e}")
                progress.update(task, completed=1)
                return False

            # Install system dependencies
            task = progress.add_task(
                "[bold green]Installing system dependencies...",
                total=len(SYSTEM_DEPENDENCIES),
            )
            for package in SYSTEM_DEPENDENCIES:
                try:
                    run_command(["apt-get", "install", "-y", package], sudo=True)
                    progress.update(
                        task,
                        advance=1,
                        description=f"[bold green]Installing {package}...",
                    )
                    print_success(f"{package} installed.")
                except Exception as e:
                    print_error(f"Failed to install {package}: {e}")
                    progress.update(task, advance=1)

            print_success("System dependencies installed successfully.")
            return True
        except Exception as e:
            print_error(f"Error installing system dependencies: {e}")
            return False


def install_pyenv() -> bool:
    """Install pyenv for the current user."""
    print_section("Installing pyenv")

    # Check if pyenv is already installed
    if os.path.exists(PYENV_DIR) and os.path.isfile(PYENV_BIN):
        print_success("pyenv is already installed.")
        return True

    print_step("Installing pyenv...")

    with Status("[bold green]Downloading pyenv installer...") as status:
        try:
            # Get the pyenv installer
            curl_cmd = ["curl", "-fsSL", "https://pyenv.run"]
            bash_cmd = ["bash"]

            installer = run_command(curl_cmd).stdout

            # Create a temporary file for the installer
            temp_installer = os.path.join("/tmp", "pyenv_installer.sh")
            with open(temp_installer, "w") as f:
                f.write(installer)

            # Make it executable
            os.chmod(temp_installer, 0o755)

            status.update("[bold green]Running pyenv installer...")

            # Run the installer
            run_command([temp_installer])

            # Check if installation was successful
            if os.path.exists(PYENV_DIR) and os.path.isfile(PYENV_BIN):
                print_success("pyenv installed successfully.")

                # Setup shell integration
                status.update("[bold green]Setting up shell configuration...")
                shell_rc_files = [
                    os.path.join(HOME_DIR, ".bashrc"),
                    os.path.join(HOME_DIR, ".zshrc"),
                ]

                pyenv_init_lines = [
                    "# pyenv initialization",
                    'export PYENV_ROOT="$HOME/.pyenv"',
                    'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"',
                    'eval "$(pyenv init -)"',
                    'eval "$(pyenv virtualenv-init -)"',
                    "",
                ]

                for rc_file in shell_rc_files:
                    if os.path.exists(rc_file):
                        with open(rc_file, "r") as f:
                            content = f.read()

                        if "pyenv init" not in content:
                            with open(rc_file, "a") as f:
                                f.write("\n" + "\n".join(pyenv_init_lines))
                            print_success(f"Added pyenv initialization to {rc_file}")

                # Update PATH for current session
                os.environ["PATH"] = f"{PYENV_DIR}/bin:{os.environ.get('PATH', '')}"

                return True
            else:
                print_error("pyenv installation failed.")
                return False

        except Exception as e:
            print_error(f"Error installing pyenv: {e}")
            return False


def install_latest_python_with_pyenv() -> bool:
    """Install the latest Python version using pyenv."""
    print_section("Installing Latest Python with pyenv")

    if not os.path.exists(PYENV_BIN):
        print_error("pyenv is not installed. Please install it first.")
        return False

    with Status("[bold green]Updating pyenv...") as status:
        try:
            # Update pyenv first
            run_command([PYENV_BIN, "update"])

            # Get latest Python version available
            status.update("[bold green]Finding latest Python version...")
            latest_version_output = run_command([PYENV_BIN, "install", "--list"]).stdout

            # Parse the output to find the latest stable Python version
            versions = re.findall(
                r"^\s*(\d+\.\d+\.\d+)$", latest_version_output, re.MULTILINE
            )
            if not versions:
                print_error("Could not find any Python versions to install.")
                return False

            # Sort versions and get the latest
            latest_version = sorted(
                versions, key=lambda v: [int(i) for i in v.split(".")]
            )[-1]

            status.update(f"[bold green]Installing Python {latest_version}...")
            console.print(
                f"Installing Python [bold]{latest_version}[/bold] (this may take several minutes)..."
            )

            # Install the latest version
            with Progress(
                SpinnerColumn(),
                TextColumn(f"[bold green]Installing Python {latest_version}..."),
                TimeRemainingColumn(),
                expand=True,
            ) as progress:
                task = progress.add_task("Installing...", total=None)
                run_command([PYENV_BIN, "install", "--skip-existing", latest_version])
                progress.update(task, completed=True)

            # Set as global Python version
            run_command([PYENV_BIN, "global", latest_version])

            # Verify installation
            pyenv_python = os.path.join(PYENV_DIR, "shims", "python")
            if os.path.exists(pyenv_python):
                python_version = run_command([pyenv_python, "--version"]).stdout
                print_success(f"Successfully installed {python_version.strip()}")

                # Update PATH for current session
                os.environ["PATH"] = f"{PYENV_DIR}/shims:{os.environ.get('PATH', '')}"

                return True
            else:
                print_error("Python installation with pyenv failed.")
                return False

        except Exception as e:
            print_error(f"Error installing Python with pyenv: {e}")
            return False


def install_pipx() -> bool:
    """Ensure pipx is installed; install it using pip if missing."""
    print_section("Installing pipx")

    if check_command_available("pipx"):
        print_success("pipx is already installed.")
        return True

    print_step("Installing pipx...")

    with Status("[bold green]Installing pipx...") as status:
        try:
            # Try to get python from pyenv first
            python_cmd = os.path.join(PYENV_DIR, "shims", "python")
            if not os.path.exists(python_cmd):
                python_cmd = shutil.which("python3") or shutil.which("python")

            if not python_cmd:
                print_error("Could not find a Python executable.")
                return False

            # Install pipx
            run_command([python_cmd, "-m", "pip", "install", "--user", "pipx"])
            run_command([python_cmd, "-m", "pipx", "ensurepath"])

            # Verify installation
            pipx_path = os.path.join(HOME_DIR, ".local", "bin", "pipx")
            if os.path.exists(pipx_path):
                # Add to PATH for current session
                os.environ["PATH"] = (
                    f"{os.path.dirname(pipx_path)}:{os.environ.get('PATH', '')}"
                )
                print_success("pipx installed successfully.")
                return True
            else:
                print_error("pipx installation could not be verified.")
                return False

        except Exception as e:
            print_error(f"Error installing pipx: {e}")
            return False


def install_pipx_tools() -> bool:
    """Install Python tools via pipx."""
    print_section("Installing Python Tools via pipx")

    if not install_pipx():
        print_error("Failed to ensure pipx installation.")
        return False

    pipx_cmd = os.path.join(HOME_DIR, ".local", "bin", "pipx")
    if not os.path.exists(pipx_cmd):
        pipx_cmd = shutil.which("pipx")

    if not pipx_cmd:
        print_error("Could not find pipx executable.")
        return False

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        expand=True,
    ) as progress:
        task = progress.add_task(
            "[bold green]Installing Python tools...", total=len(PIPX_TOOLS)
        )
        failed_tools = []

        for tool in PIPX_TOOLS:
            try:
                progress.update(task, description=f"[bold green]Installing {tool}...")
                run_command([pipx_cmd, "install", tool, "--force"])
                progress.update(task, advance=1)
                print_success(f"Installed {tool} via pipx.")
            except Exception as e:
                print_warning(f"Failed to install {tool}: {e}")
                failed_tools.append(tool)
                progress.update(task, advance=1)

        if failed_tools:
            print_warning(
                f"Failed to install the following tools: {', '.join(failed_tools)}"
            )
            return False

        print_success("Python tools installation completed.")
        return True


# ==============================
# Menu System
# ==============================
def interactive_menu() -> None:
    """Display the main menu and handle user selection."""
    while True:
        clear_screen()
        print_header(APP_NAME)

        # System info panel
        info = Table.grid(padding=1)
        info.add_column(style=f"bold {NordColors.NORD9}")
        info.add_column(style=f"{NordColors.NORD4}")

        info.add_row("Version:", VERSION)
        info.add_row("System:", f"{platform.system()} {platform.release()}")
        info.add_row("Python:", platform.python_version())
        info.add_row("User:", os.environ.get("USER", "Unknown"))

        # Check if pyenv is installed
        pyenv_status = "Installed" if os.path.exists(PYENV_BIN) else "Not installed"
        info.add_row("pyenv:", pyenv_status)

        # Check if pipx is installed
        pipx_status = (
            "Installed" if check_command_available("pipx") else "Not installed"
        )
        info.add_row("pipx:", pipx_status)

        console.print(
            Panel(info, title="System Information", border_style=f"{NordColors.NORD9}")
        )

        # Main menu options
        menu_options = [
            ("1", "Check System Compatibility"),
            ("2", "Install System Dependencies"),
            ("3", "Install pyenv"),
            ("4", "Install Latest Python with pyenv"),
            ("5", "Install pipx and Python Tools"),
            ("6", "Run Full Setup"),
            ("0", "Exit"),
        ]

        console.print(create_menu_table("Main Menu", menu_options))

        # Get user selection
        choice = get_user_input("Enter your choice (0-6):")

        if choice == "1":
            check_system()
            pause()
        elif choice == "2":
            install_system_dependencies()
            pause()
        elif choice == "3":
            install_pyenv()
            pause()
        elif choice == "4":
            install_latest_python_with_pyenv()
            pause()
        elif choice == "5":
            install_pipx_tools()
            pause()
        elif choice == "6":
            run_full_setup()
            pause()
        elif choice == "0":
            clear_screen()
            print_header("Goodbye!")
            console.print(
                Panel(
                    "Thank you for using the Python Dev Setup Tool.",
                    border_style=f"bold {NordColors.NORD14}",
                )
            )
            time.sleep(1)
            sys.exit(0)
        else:
            print_error("Invalid selection. Please try again.")
            time.sleep(1)


def run_full_setup() -> None:
    """Run the complete setup process."""
    print_section("Full Python Dev Setup")

    if not check_system():
        print_error("System check failed. Please resolve issues before continuing.")
        return

    # Install system dependencies
    print_step("Installing system dependencies...")
    if not install_system_dependencies():
        print_warning("Some system dependencies may not have been installed.")
        if not get_user_confirmation("Continue with the setup process?"):
            print_warning("Setup aborted.")
            return

    # Install pyenv
    print_step("Installing pyenv...")
    if not install_pyenv():
        print_warning("pyenv installation failed.")
        if not get_user_confirmation("Continue without pyenv?"):
            print_warning("Setup aborted.")
            return

    # Install latest Python with pyenv
    print_step("Installing latest Python version with pyenv...")
    if not install_latest_python_with_pyenv():
        print_warning("Python installation with pyenv failed.")
        if not get_user_confirmation("Continue without latest Python?"):
            print_warning("Setup aborted.")
            return

    # Install pipx and Python tools
    print_step("Installing pipx and Python tools...")
    if not install_pipx_tools():
        print_warning("Some Python tools may not have been installed.")

    # Final summary
    print_section("Setup Summary")
    summary = Table(title="Installation Results", box=box.ROUNDED)
    summary.add_column("Component", style=f"bold {NordColors.NORD9}")
    summary.add_column("Status", style=f"{NordColors.NORD4}")

    summary.add_row(
        "System Dependencies",
        "[bold green]✓ Installed[/]"
        if check_command_available("gcc")
        else "[bold red]× Failed[/]",
    )

    summary.add_row(
        "pyenv",
        "[bold green]✓ Installed[/]"
        if os.path.exists(PYENV_BIN)
        else "[bold red]× Failed[/]",
    )

    python_installed = os.path.exists(os.path.join(PYENV_DIR, "shims", "python"))
    summary.add_row(
        "Python (via pyenv)",
        "[bold green]✓ Installed[/]" if python_installed else "[bold red]× Failed[/]",
    )

    summary.add_row(
        "pipx",
        "[bold green]✓ Installed[/]"
        if check_command_available("pipx")
        else "[bold red]× Failed[/]",
    )

    console.print(summary)

    # Shell reloading instructions
    shell_name = os.path.basename(os.environ.get("SHELL", "bash"))
    console.print(
        Panel(
            f"To fully apply all changes, you should restart your terminal or run:\n\nsource ~/.{shell_name}rc",
            title="Next Steps",
            border_style=f"bold {NordColors.NORD13}",
        )
    )

    print_success("Setup process completed!")


# ==============================
# Main Entry Point
# ==============================
def main() -> None:
    """Main entry point for the script."""
    try:
        # Setup signal handlers
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            signal.signal(sig, signal_handler)

        # Check if running as root
        if is_root():
            console.print(
                Panel(
                    "This script should NOT be run as root. Please run it as a regular user.\n"
                    "It will use sudo when necessary for system-level operations.",
                    title="⚠️ Warning",
                    border_style=f"bold {NordColors.NORD11}",
                )
            )
            if not get_user_confirmation("Do you want to continue anyway?"):
                sys.exit(1)

        # Launch the interactive menu
        interactive_menu()

    except KeyboardInterrupt:
        print_warning("\nProcess interrupted by user.")
        sys.exit(130)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_warning("Setup interrupted by user.")
        sys.exit(130)
    except Exception as e:
        print_error(f"Unhandled error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
