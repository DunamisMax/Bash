#!/usr/bin/env python3
"""
Install Virtualization Packages and Enable Default Network Switch for Ubuntu

This script installs common virtualization packages (QEMU/KVM, libvirt, etc.)
and then enables the default NAT network switch for virtual machines.
It uses only the standard library, provides clear, color-coded output,
and handles interrupts gracefully.

Note: Run this script with root privileges.
"""

import os
import signal
import subprocess
import sys
import time
from typing import List


# ANSI color codes for terminal output
class Colors:
    HEADER = "\033[95m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"


# List of virtualization packages to install
PACKAGES: List[str] = [
    "qemu-kvm",
    "qemu-utils",
    "libvirt-daemon-system",
    "libvirt-clients",
    "virt-manager",
    "bridge-utils",
    "cpu-checker",
    "ovmf",
    "virtinst",
]


def signal_handler(sig, frame) -> None:
    """Handle interrupt signals gracefully."""
    print(f"\n{Colors.YELLOW}Installation interrupted. Exiting...{Colors.ENDC}")
    sys.exit(1)


def run_command(cmd: List[str]) -> bool:
    """
    Run a command and stream its output.

    Args:
        cmd: A list of command arguments.

    Returns:
        True if the command succeeds, False otherwise.
    """
    try:
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        while True:
            line = process.stdout.readline()
            if not line:
                break
            sys.stdout.write(line)
        process.wait()
        if process.returncode != 0:
            print(
                f"{Colors.RED}Command {' '.join(cmd)} failed with exit code {process.returncode}.{Colors.ENDC}"
            )
            return False
        return True
    except Exception as e:
        print(f"{Colors.RED}Error running command {' '.join(cmd)}: {e}{Colors.ENDC}")
        return False


def print_header(message: str) -> None:
    """Print a formatted header message."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 60}")
    print(message.center(60))
    print(f"{'=' * 60}{Colors.ENDC}\n")


def install_packages(packages: List[str]) -> None:
    """Install each package one by one."""
    for idx, pkg in enumerate(packages, start=1):
        print_header(f"Installing package {idx}/{len(packages)}: {pkg}")
        if not run_command(["apt-get", "install", "-y", pkg]):
            print(
                f"{Colors.RED}Failed to install {pkg}. Aborting installation.{Colors.ENDC}"
            )
            sys.exit(1)
        else:
            print(f"{Colors.GREEN}Successfully installed {pkg}.{Colors.ENDC}")
        time.sleep(1)


def enable_default_network() -> None:
    """
    Enable the default network switch for virtual machines.

    This function starts the 'default' network and sets it to autostart
    using the 'virsh' command.
    """
    print_header("Enabling default network switch for virtual machines")

    # Start the default network
    if run_command(["virsh", "net-start", "default"]):
        print(f"{Colors.GREEN}Default network started successfully.{Colors.ENDC}")
    else:
        print(
            f"{Colors.YELLOW}Default network may already be running or failed to start.{Colors.ENDC}"
        )

    # Enable autostart for the default network
    if run_command(["virsh", "net-autostart", "default"]):
        print(
            f"{Colors.GREEN}Default network set to autostart successfully.{Colors.ENDC}"
        )
    else:
        print(
            f"{Colors.YELLOW}Failed to set default network to autostart. It may already be enabled.{Colors.ENDC}"
        )


def main() -> None:
    """Main execution function."""
    # Handle signals for graceful termination
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Check for root privileges
    if os.geteuid() != 0:
        print(
            f"{Colors.RED}Error: This script must be run with root privileges.{Colors.ENDC}"
        )
        sys.exit(1)

    print_header("Updating package lists")
    if not run_command(["apt-get", "update"]):
        print(f"{Colors.RED}Failed to update package lists. Aborting.{Colors.ENDC}")
        sys.exit(1)

    print_header("Installing virtualization packages")
    install_packages(PACKAGES)

    enable_default_network()

    print_header("Installation Complete")
    print(
        f"{Colors.GREEN}All virtualization packages installed and default network enabled successfully.{Colors.ENDC}"
    )


if __name__ == "__main__":
    main()
