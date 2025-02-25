#!/usr/bin/env python3
"""
Unified Backup Script for System Backup to Backblaze B2
--------------------------------------------------------
Description:
  This script uses restic to perform a system backup directly to a Backblaze B2 repository.
  The repository is automatically named after the hostname of the system on which the script is run.
  If the repository does not exist, it is automatically initialized.
  After backup, a retention policy is enforced (removing snapshots older than a specified number of days).

Usage:
  sudo ./unified_backup.py

Author: Your Name | License: MIT | Version: 2.2.0
"""

import atexit
import logging
import os
import shutil
import signal
import socket
import subprocess
import sys

# ------------------------------------------------------------------------------
# Environment Configuration (Modify these settings as needed)
# ------------------------------------------------------------------------------
# Backblaze B2 Backup Repository Credentials and Bucket
B2_ACCOUNT_ID = "your_b2_account_id"
B2_ACCOUNT_KEY = "your_b2_account_key"
B2_BUCKET_SYSTEM = "your_b2_system_bucket"

# Determine the hostname to uniquely name the repository
HOSTNAME = socket.gethostname()
# Restic repository string for B2 follows the format: b2:bucket:directory
B2_REPO_SYSTEM = f"b2:{B2_BUCKET_SYSTEM}:{HOSTNAME}"

# Unified Restic Repository Password (use one strong, secure password everywhere)
RESTIC_PASSWORD = "your_unified_restic_password"

# Backup Source Directory and Exclusions
SYSTEM_SOURCE = "/"  # Backup the entire system

SYSTEM_EXCLUDES = [
    # Virtual / dynamic filesystems – always exclude these.
    "/proc/*",
    "/sys/*",
    "/dev/*",
    "/run/*",
    
    # Temporary directories (often changing, transient, or recreated on boot)
    "/tmp/*",
    "/var/tmp/*",
    
    # Mount points and removable media (to avoid backing up external or transient mounts)
    "/mnt/*",
    "/media/*",
    
    # Common cache directories that need not be backed up
    "/var/cache/*",
    "/var/log/*",
    # User-level cache folders (if you wish to exclude them; adjust as needed)
    "/home/*/.cache/*",
    
    # Swap file, lost+found, and other system artifacts
    "/swapfile",
    "/lost+found",
    
    # Exclude VM disk images (common locations and file extensions)
    "*.vmdk",     # VMware disk image
    "*.vdi",      # VirtualBox disk image
    "*.qcow2",    # QEMU/KVM disk image
    "*.img",      # Generic disk image (use with caution if you also have valid .img files)
    
    # Other large, transient files
    "*.iso",      # Disc images
    "*.tmp",
    "*.swap.img",
    
    # Exclude specific directories known to store ephemeral or large nonessential data
    "/var/lib/docker/*",  # Docker images/containers (if not intended to be backed up)
    "/var/lib/lxc/*",     # LXC containers (if not intended to be backed up)
]


# Retention policy (keep snapshots within this many days)
RETENTION_DAYS = 7

# Logging Configuration
LOG_FILE = "/var/log/unified_backup.log"
DEFAULT_LOG_LEVEL = "INFO"
# ------------------------------------------------------------------------------

def setup_logging():
    log_dir = os.path.dirname(LOG_FILE)
    if not os.path.isdir(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, DEFAULT_LOG_LEVEL),
        format="[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stderr), logging.FileHandler(LOG_FILE)],
    )
    try:
        os.chmod(LOG_FILE, 0o600)
    except Exception as e:
        logging.warning(f"Failed to set permissions on log file {LOG_FILE}: {e}")

setup_logging()

def print_section(title: str):
    border = "─" * 60
    logging.info(border)
    logging.info(f"  {title}")
    logging.info(border)

def signal_handler(signum, frame):
    logging.error("Script interrupted by signal.")
    sys.exit(130)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def cleanup():
    logging.info("Performing cleanup tasks before exit.")
    # Additional cleanup tasks can be added here.

atexit.register(cleanup)

def check_dependencies():
    if not shutil.which("restic"):
        logging.error("The 'restic' binary is not found in your PATH. Please install restic and try again.")
        sys.exit(1)

def run_restic(repo: str, password: str, *args):
    env = os.environ.copy()
    env["RESTIC_PASSWORD"] = password
    if repo.startswith("b2:"):
        env["B2_ACCOUNT_ID"] = B2_ACCOUNT_ID
        env["B2_ACCOUNT_KEY"] = B2_ACCOUNT_KEY
    cmd = ["restic", "--repo", repo] + list(args)
    logging.info(f"Running restic command: {' '.join(cmd)}")
    subprocess.run(cmd, check=True, env=env)

def is_local_repo(repo: str) -> bool:
    """Determine if the repository is local (i.e., not a B2 repo)."""
    return not repo.startswith("b2:")

def ensure_repo_initialized(repo: str, password: str):
    """
    Ensures that a restic repository is initialized.
    For local repositories, check if the 'config' file exists.
    For B2 repositories, attempt a snapshots command.
    """
    if is_local_repo(repo):
        config_path = os.path.join(repo, "config")
        if os.path.exists(config_path):
            logging.info(f"Repository '{repo}' already initialized.")
            return
        else:
            logging.info(f"Repository '{repo}' not initialized. Initializing...")
            run_restic(repo, password, "init")
    else:
        try:
            run_restic(repo, password, "snapshots")
            logging.info(f"Repository '{repo}' already initialized.")
        except subprocess.CalledProcessError:
            logging.info(f"Repository '{repo}' not initialized. Initializing...")
            run_restic(repo, password, "init")

def backup_repo(repo: str, password: str, source: str, excludes: list = None):
    if excludes is None:
        excludes = []
    ensure_repo_initialized(repo, password)
    cmd_args = ["backup", source]
    for pattern in excludes:
        cmd_args.extend(["--exclude", pattern])
    run_restic(repo, password, *cmd_args)

def cleanup_repo(repo: str, password: str, retention_days: int):
    ensure_repo_initialized(repo, password)
    run_restic(repo, password, "forget", "--prune", "--keep-within", f"{retention_days}d")

def main():
    check_dependencies()

    if os.geteuid() != 0:
        logging.error("This script must be run as root.")
        sys.exit(1)

    logging.info("Unified backup script started.")

    backup_tasks = [
        {
            "description": "Backup System to Backblaze B2 Repository",
            "repo": B2_REPO_SYSTEM,
            "source": SYSTEM_SOURCE,
            "excludes": SYSTEM_EXCLUDES,
        },
    ]

    for task in backup_tasks:
        print_section(task["description"])
        try:
            backup_repo(task["repo"], RESTIC_PASSWORD, task["source"], task["excludes"])
        except subprocess.CalledProcessError as e:
            logging.error(f"{task['description']} failed with error: {e}")
            sys.exit(e.returncode)

    print_section("Cleaning Up Old Snapshots (Retention Policy)")
    try:
        logging.info("Cleaning Backblaze B2 System Repository...")
        cleanup_repo(B2_REPO_SYSTEM, RESTIC_PASSWORD, RETENTION_DAYS)
    except subprocess.CalledProcessError as e:
        logging.error(f"Cleanup failed: {e}")
        sys.exit(e.returncode)

    logging.info("Unified backup script completed successfully.")

if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        logging.error(f"Unhandled exception: {ex}")
        sys.exit(1)
