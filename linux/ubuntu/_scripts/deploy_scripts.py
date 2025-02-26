#!/usr/bin/env python3
"""
Script Name: deploy_scripts.py
--------------------------------------------------------
Description:
  Deploys user scripts from a source directory to a target directory
  on Ubuntu Linux. Ensures proper ownership, performs a dry-run, and
  sets executable permissions using a Nord-themed enhanced template for
  robust error handling and logging.

Usage:
  sudo ./deploy_scripts.py

Author: Your Name | License: MIT | Version: 3.0.0
"""

import atexit
import logging
import os
import pwd
import signal
import subprocess
import sys
import shutil
from datetime import datetime

# ------------------------------------------------------------------------------
# Environment Configuration (Modify these settings as needed)
# ------------------------------------------------------------------------------
LOG_FILE = "/var/log/deploy-scripts.log"
DISABLE_COLORS = os.environ.get("DISABLE_COLORS", "false").lower() == "true"
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

# Deployment-specific configuration
SCRIPT_SOURCE = "/home/sawyer/github/bash/linux/ubuntu/_scripts"
SCRIPT_TARGET = "/home/sawyer/bin"
EXPECTED_OWNER = "sawyer"

# ------------------------------------------------------------------------------
# NORD COLOR THEME CONSTANTS (24-bit ANSI escape sequences)
# ------------------------------------------------------------------------------
NORD0 = "\033[38;2;46;52;64m"  # Polar Night (dark)
NORD1 = "\033[38;2;59;66;82m"  # Polar Night (darker than NORD0)
NORD2 = "\033[38;2;67;76;94m"  # Polar Night (darker than NORD1)
NORD3 = "\033[38;2;76;86;106m"  # Polar Night (darker than NORD2)
NORD4 = "\033[38;2;216;222;233m"  # Snow Storm (lightest)
NORD5 = "\033[38;2;229;233;240m"  # Snow Storm (middle)
NORD6 = "\033[38;2;236;239;244m"  # Snow Storm (darkest)
NORD7 = "\033[38;2;143;188;187m"  # Frost
NORD8 = "\033[38;2;136;192;208m"  # Frost (light blue)
NORD9 = "\033[38;2;129;161;193m"  # Bluish (DEBUG)
NORD10 = "\033[38;2;94;129;172m"  # Accent Blue (section headers)
NORD11 = "\033[38;2;191;97;106m"  # Reddish (ERROR/CRITICAL)
NORD12 = "\033[38;2;208;135;112m"  # Aurora (orange)
NORD13 = "\033[38;2;235;203;139m"  # Yellowish (WARN)
NORD14 = "\033[38;2;163;190;140m"  # Greenish (INFO)
NORD15 = "\033[38;2;180;142;173m"  # Purple
NC = "\033[0m"  # Reset / No Color

# ------------------------------------------------------------------------------
# CUSTOM LOGGING
# ------------------------------------------------------------------------------


class NordColorFormatter(logging.Formatter):
    """
    A custom formatter that applies Nord color theme to log messages.
    """

    def __init__(self, fmt=None, datefmt=None, use_colors=True):
        super().__init__(fmt, datefmt)
        self.use_colors = use_colors and not DISABLE_COLORS

    def format(self, record):
        levelname = record.levelname
        msg = super().format(record)

        if not self.use_colors:
            return msg

        if levelname == "DEBUG":
            return f"{NORD9}{msg}{NC}"
        elif levelname == "INFO":
            return f"{NORD14}{msg}{NC}"
        elif levelname == "WARNING":
            return f"{NORD13}{msg}{NC}"
        elif levelname in ("ERROR", "CRITICAL"):
            return f"{NORD11}{msg}{NC}"
        return msg


def setup_logging():
    """
    Set up logging with console and file handlers, using Nord color theme.
    """
    log_dir = os.path.dirname(LOG_FILE)
    if not os.path.isdir(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    # Create logger
    logger = logging.getLogger()
    numeric_level = getattr(logging, LOG_LEVEL, logging.INFO)
    logger.setLevel(numeric_level)

    # Clear any existing handlers
    for handler in list(logger.handlers):
        logger.removeHandler(handler)

    # Console handler with colors
    console_formatter = NordColorFormatter(
        fmt="[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler (no colors in file)
    file_formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    try:
        os.chmod(LOG_FILE, 0o600)
    except Exception as e:
        logger.warning(f"Failed to set permissions on log file {LOG_FILE}: {e}")

    return logger


def print_section(title: str):
    """
    Print a section header with Nord theme styling.
    """
    if not DISABLE_COLORS:
        border = "─" * 60
        logging.info(f"{NORD10}{border}{NC}")
        logging.info(f"{NORD10}  {title}{NC}")
        logging.info(f"{NORD10}{border}{NC}")
    else:
        border = "─" * 60
        logging.info(border)
        logging.info(f"  {title}")
        logging.info(border)


# ------------------------------------------------------------------------------
# SIGNAL HANDLING & CLEANUP
# ------------------------------------------------------------------------------


def signal_handler(signum, frame):
    """
    Handle termination signals gracefully.
    """
    if signum == signal.SIGINT:
        logging.error("Script interrupted by SIGINT (Ctrl+C).")
        sys.exit(130)
    elif signum == signal.SIGTERM:
        logging.error("Script terminated by SIGTERM.")
        sys.exit(143)
    else:
        logging.error(f"Script interrupted by signal {signum}.")
        sys.exit(128 + signum)


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def cleanup():
    """
    Perform cleanup tasks before exit.
    """
    logging.info("Performing cleanup tasks before exit.")
    # Additional cleanup tasks can be added here


atexit.register(cleanup)

# ------------------------------------------------------------------------------
# DEPENDENCY CHECKING
# ------------------------------------------------------------------------------


def check_dependencies():
    """
    Check for required dependencies.
    """
    required_commands = ["rsync", "find"]
    for cmd in required_commands:
        if not shutil.which(cmd):
            logging.error(
                f"The '{cmd}' command is not found in your PATH. Please install it and try again."
            )
            sys.exit(1)


# ------------------------------------------------------------------------------
# HELPER & UTILITY FUNCTIONS
# ------------------------------------------------------------------------------


def check_root():
    """
    Ensure the script is run with root privileges.
    """
    if os.geteuid() != 0:
        logging.error("This script must be run as root.")
        sys.exit(1)


# ------------------------------------------------------------------------------
# DEPLOYMENT FUNCTION
# ------------------------------------------------------------------------------


def deploy_user_scripts():
    """
    Deploy user scripts from source to target directory.
    """
    print_section("Deploying User Scripts")
    logging.info("Starting deployment of user scripts...")

    # 1. Check ownership of source directory.
    try:
        stat_info = os.stat(SCRIPT_SOURCE)
        source_owner = pwd.getpwuid(stat_info.st_uid).pw_name
    except Exception as e:
        logging.error(f"Failed to stat source directory: {SCRIPT_SOURCE}. Error: {e}")
        sys.exit(1)

    if source_owner != EXPECTED_OWNER:
        logging.error(
            f"Invalid script source ownership for '{SCRIPT_SOURCE}' (Owner: {source_owner}). Expected: {EXPECTED_OWNER}"
        )
        sys.exit(1)

    # 2. Perform a dry-run deployment.
    logging.info("Performing dry-run for script deployment...")
    dry_run_cmd = [
        "rsync",
        "--dry-run",
        "-ah",
        "--delete",
        f"{SCRIPT_SOURCE}/",
        SCRIPT_TARGET,
    ]
    try:
        result = subprocess.run(dry_run_cmd, check=True, capture_output=True, text=True)
        logging.debug(f"Dry-run output: {result.stdout}")
    except subprocess.CalledProcessError as e:
        logging.error(f"Dry-run failed for script deployment: {e.stderr}")
        sys.exit(1)

    # 3. Actual deployment.
    logging.info(f"Deploying scripts from '{SCRIPT_SOURCE}' to '{SCRIPT_TARGET}'...")
    deploy_cmd = ["rsync", "-ah", "--delete", f"{SCRIPT_SOURCE}/", SCRIPT_TARGET]
    try:
        result = subprocess.run(deploy_cmd, check=True, capture_output=True, text=True)
        logging.debug(f"Deployment output: {result.stdout}")
    except subprocess.CalledProcessError as e:
        logging.error(f"Script deployment failed: {e.stderr}")
        sys.exit(1)

    # 4. Set executable permissions on deployed scripts.
    logging.info("Setting executable permissions on deployed scripts...")
    chmod_cmd = f"find {SCRIPT_TARGET} -type f -exec chmod 755 {{}} \\;"
    try:
        subprocess.run(chmod_cmd, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to update script permissions in '{SCRIPT_TARGET}': {e}")
        sys.exit(1)

    logging.info("Script deployment completed successfully.")


# ------------------------------------------------------------------------------
# MAIN ENTRY POINT
# ------------------------------------------------------------------------------


def main():
    """
    Main entry point for the script.
    """
    # Ensure the log directory exists before we attempt to log anything
    log_dir = os.path.dirname(LOG_FILE)
    if not os.path.isdir(log_dir):
        try:
            os.makedirs(log_dir, exist_ok=True)
        except Exception as e:
            print(f"Failed to create log directory: {log_dir}. Error: {e}")
            sys.exit(1)

    try:
        with open(LOG_FILE, "a"):
            pass
        os.chmod(LOG_FILE, 0o600)
    except Exception as e:
        print(
            f"Failed to create or set permissions on log file: {LOG_FILE}. Error: {e}"
        )
        sys.exit(1)

    setup_logging()
    check_root()
    check_dependencies()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logging.info("=" * 80)
    logging.info(f"SCRIPT STARTED AT {now}")
    logging.info("=" * 80)

    # Execute main function
    deploy_user_scripts()

    # Finish up
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logging.info("=" * 80)
    logging.info(f"SCRIPT COMPLETED SUCCESSFULLY AT {now}")
    logging.info("=" * 80)


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        # This catches any unhandled exceptions
        if "logging" in sys.modules:
            logging.error(f"Unhandled exception: {ex}")
        else:
            print(f"Unhandled exception: {ex}")
        sys.exit(1)
