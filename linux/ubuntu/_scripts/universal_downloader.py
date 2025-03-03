#!/usr/bin/env python3
"""
Enhanced Universal Downloader Script
-------------------------------------

This utility downloads files from the web using either wget (for general files)
or yt-dlp (for YouTube videos/playlists). It provides real-time progress tracking,
automatic dependency checking and installation, comprehensive error handling,
and a beautiful Nord-themed terminal interface.

Note: For full functionality (especially dependency installation), run with root privileges.
Version: 3.2.0
"""

import atexit
import datetime
import os
import platform
import re
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Third-party libraries
from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    TimeRemainingColumn,
)
import pyfiglet

# ------------------------------
# Configuration & Constants
# ------------------------------
HOSTNAME = socket.gethostname()
VERSION = "3.2.0"
LOG_FILE = "/var/log/universal_downloader.log"
DEFAULT_DOWNLOAD_DIR = os.path.expanduser("~/Downloads")

# Define dependency groups
DEPENDENCIES = {
    "common": ["curl"],
    "wget": ["wget"],
    "yt-dlp": ["yt-dlp", "ffmpeg"],
}

# Progress display settings
PROGRESS_WIDTH = 50
SPINNER_INTERVAL = 0.1  # seconds between spinner updates
TERM_WIDTH = min(shutil.get_terminal_size().columns, 100)

# ------------------------------
# Nord-Themed Console Setup
# ------------------------------
console = Console()


def print_header(text: str) -> None:
    """Display a large header using pyfiglet with Nord colors."""
    ascii_art = pyfiglet.figlet_format(text, font="slant")
    console.print(ascii_art, style="bold #88C0D0")


def print_section(title: str) -> None:
    """Print a formatted section header."""
    border = "═" * TERM_WIDTH
    console.print(f"\n[bold #88C0D0]{border}[/bold #88C0D0]")
    console.print(f"[bold #88C0D0]  {title.center(TERM_WIDTH - 4)}[/bold #88C0D0]")
    console.print(f"[bold #88C0D0]{border}[/bold #88C0D0]\n")


def print_info(message: str) -> None:
    """Print an informational message."""
    console.print(f"[#81A1C1]{message}[/#81A1C1]")


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[bold #A3BE8C]✓ {message}[/bold #A3BE8C]")


def print_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"[bold #EBCB8B]⚠ {message}[/bold #EBCB8B]")


def print_error(message: str) -> None:
    """Print an error message."""
    console.print(f"[bold #BF616A]✗ {message}[/bold #BF616A]")


def print_step(text: str) -> None:
    """Print a step description."""
    console.print(f"[#88C0D0]• {text}[/#88C0D0]")


def format_size(num_bytes: float) -> str:
    """Convert bytes to a human-readable string."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} PB"


# ------------------------------
# Logging Setup
# ------------------------------
def setup_logging(log_file: str = LOG_FILE) -> None:
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


# ------------------------------
# Signal Handling & Cleanup
# ------------------------------
def cleanup() -> None:
    """Perform any necessary cleanup before exiting."""
    print_step("Performing cleanup tasks...")


atexit.register(cleanup)


def signal_handler(signum, frame) -> None:
    """Handle termination signals gracefully."""
    sig_name = (
        signal.Signals(signum).name
        if hasattr(signal, "Signals")
        else f"signal {signum}"
    )
    print_warning(f"Script interrupted by {sig_name}.")
    cleanup()
    sys.exit(128 + signum)


for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
    signal.signal(sig, signal_handler)


# ------------------------------
# Progress Tracking Classes
# ------------------------------
class ProgressBar:
    """
    A thread-safe progress bar that displays transfer progress,
    estimated transfer rate, and ETA.
    """

    def __init__(self, total: int, desc: str = "", width: int = PROGRESS_WIDTH) -> None:
        self.total = max(1, total)
        self.desc = desc
        self.width = width
        self.current = 0
        self.start_time = time.time()
        self.last_update_time = self.start_time
        self.last_update_value = 0
        self.rates: List[float] = []
        self._lock = threading.Lock()
        self._display()

    def update(self, amount: int) -> None:
        """Update the progress by a given amount."""
        with self._lock:
            self.current = min(self.current + amount, self.total)
            now = time.time()
            if now - self.last_update_time >= 0.5:
                delta = self.current - self.last_update_value
                rate = delta / (now - self.last_update_time)
                self.rates.append(rate)
                if len(self.rates) > 5:
                    self.rates.pop(0)
                self.last_update_time = now
                self.last_update_value = self.current
            self._display()

    def _display(self) -> None:
        """Render the progress bar."""
        filled = int(self.width * self.current / self.total)
        bar = "█" * filled + "░" * (self.width - filled)
        percent = self.current / self.total * 100
        elapsed = time.time() - self.start_time
        avg_rate = sum(self.rates) / max(1, len(self.rates))
        eta = (self.total - self.current) / max(0.1, avg_rate) if avg_rate > 0 else 0

        eta_str = (
            f"{eta / 3600:.1f}h"
            if eta > 3600
            else f"{eta / 60:.1f}m"
            if eta > 60
            else f"{eta:.0f}s"
        )
        console.print(
            f"\r[#88C0D0]{self.desc}:[/#88C0D0] |[#5E81AC]{bar}[/#5E81AC]| "
            f"[#D8DEE9]{percent:5.1f}%[/#D8DEE9] "
            f"({format_size(self.current)}/{format_size(self.total)}) "
            f"[[#A3BE8C]{format_size(avg_rate)}/s[/#A3BE8C]] [ETA: {eta_str}]",
            end="",
        )
        if self.current >= self.total:
            console.print()


class Spinner:
    """
    A thread-safe spinner for indicating indeterminate progress.
    """

    def __init__(self, message: str) -> None:
        self.message = message
        self.spinner_chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        self.current = 0
        self.spinning = False
        self.thread: Optional[threading.Thread] = None
        self.start_time = 0
        self._lock = threading.Lock()

    def _spin(self) -> None:
        while self.spinning:
            elapsed = time.time() - self.start_time
            time_str = f"{elapsed:.1f}s"
            with self._lock:
                console.print(
                    f"\r[#5E81AC]{self.spinner_chars[self.current]}[/#5E81AC] "
                    f"[#88C0D0]{self.message}[/#88C0D0] "
                    f"[[dim]elapsed: {time_str}[/dim]]",
                    end="",
                )
                self.current = (self.current + 1) % len(self.spinner_chars)
            time.sleep(SPINNER_INTERVAL)

    def start(self) -> None:
        """Start the spinner in a separate thread."""
        with self._lock:
            self.spinning = True
            self.start_time = time.time()
            self.thread = threading.Thread(target=self._spin, daemon=True)
            self.thread.start()

    def stop(self, success: bool = True) -> None:
        """Stop the spinner and display final message."""
        with self._lock:
            self.spinning = False
            if self.thread:
                self.thread.join()
            elapsed = time.time() - self.start_time
            time_str = (
                f"{elapsed / 3600:.1f}h"
                if elapsed > 3600
                else f"{elapsed / 60:.1f}m"
                if elapsed > 60
                else f"{elapsed:.1f}s"
            )
            # Clear the current line
            console.print("\r" + " " * TERM_WIDTH, end="\r")
            if success:
                console.print(
                    f"[#A3BE8C]✓[/#A3BE8C] [#88C0D0]{self.message}[/#88C0D0] "
                    f"[#A3BE8C]completed[/#A3BE8C] in {time_str}"
                )
            else:
                console.print(
                    f"[#BF616A]✗[/#BF616A] [#88C0D0]{self.message}[/#88C0D0] "
                    f"[#BF616A]failed[/#BF616A] after {time_str}"
                )

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop(success=exc_type is None)


# ------------------------------
# Helper Functions
# ------------------------------
def run_command(
    cmd: List[str],
    env: Optional[Dict[str, str]] = None,
    check: bool = True,
    capture_output: bool = False,
    verbose: bool = False,
) -> subprocess.CompletedProcess:
    """Execute a shell command and return the completed process."""
    if verbose:
        print_step(f"Executing: {' '.join(cmd)}")
    try:
        return subprocess.run(
            cmd,
            env=env or os.environ.copy(),
            check=check,
            text=True,
            capture_output=capture_output,
        )
    except subprocess.CalledProcessError as e:
        print_error(f"Command failed: {' '.join(cmd)}")
        if e.stderr:
            print_error(f"Error details: {e.stderr.strip()}")
        raise


def ensure_directory(path: str) -> None:
    """Ensure that a directory exists, creating it if necessary."""
    try:
        os.makedirs(path, exist_ok=True)
        print_step(f"Directory ensured: {path}")
    except Exception as e:
        print_error(f"Failed to create directory '{path}': {e}")
        sys.exit(1)


def get_file_size(url: str) -> int:
    """
    Retrieve the file size in bytes using a HEAD request with curl.
    Returns 0 if the size cannot be determined.
    """
    try:
        result = run_command(["curl", "--silent", "--head", url], capture_output=True)
        for line in result.stdout.splitlines():
            if "content-length:" in line.lower():
                return int(line.split(":", 1)[1].strip())
        return 0
    except Exception as e:
        print_warning(f"Could not determine file size for {url}: {e}")
        return 0


def estimate_youtube_size(url: str) -> int:
    """
    Estimate the file size of a YouTube video using yt-dlp.
    Falls back to a default size if estimation fails.
    """
    try:
        result = run_command(
            ["yt-dlp", "--print", "filesize", url], capture_output=True, check=False
        )
        if result.stdout.strip().isdigit():
            return int(result.stdout.strip())
        # Try estimating based on video duration
        result = run_command(
            ["yt-dlp", "--print", "duration", url], capture_output=True, check=False
        )
        if result.stdout.strip().replace(".", "", 1).isdigit():
            duration = float(result.stdout.strip())
            # Rough estimate: Assume 10 MB per minute of video
            return int(duration * 60 * 10 * 1024)
        return 100 * 1024 * 1024  # Default 100MB
    except Exception as e:
        print_warning(f"Could not estimate video size: {e}")
        return 100 * 1024 * 1024


def check_root_privileges() -> bool:
    """Return True if running as root, otherwise warn the user."""
    if os.geteuid() != 0:
        print_warning("Not running with root privileges. Some features may be limited.")
        return False
    return True


def check_dependencies(required: List[str]) -> bool:
    """Check that all required commands are available."""
    missing = [cmd for cmd in required if not shutil.which(cmd)]
    if missing:
        print_warning(f"Missing dependencies: {', '.join(missing)}")
        return False
    return True


def install_dependencies(deps: List[str], verbose: bool = False) -> bool:
    """Attempt to install missing dependencies using apt."""
    print_section(f"Installing Dependencies: {', '.join(deps)}")
    try:
        with Spinner("Updating package lists"):
            run_command(["apt", "update"], verbose=verbose, capture_output=not verbose)
        with Spinner(f"Installing {len(deps)} packages"):
            run_command(
                ["apt", "install", "-y"] + deps,
                verbose=verbose,
                capture_output=not verbose,
            )
        missing = [cmd for cmd in deps if not shutil.which(cmd)]
        if missing:
            print_error(f"Failed to install: {', '.join(missing)}")
            return False
        print_success(f"Successfully installed: {', '.join(deps)}")
        return True
    except Exception as e:
        print_error(f"Failed to install dependencies: {e}")
        return False


def check_internet_connectivity() -> bool:
    """Check for internet connectivity by pinging a well-known host."""
    try:
        result = run_command(
            ["ping", "-c", "1", "-W", "2", "8.8.8.8"], check=False, capture_output=True
        )
        return result.returncode == 0
    except Exception:
        return False


# ------------------------------
# Download Functions
# ------------------------------
def download_with_wget(url: str, output_dir: str, verbose: bool = False) -> bool:
    """
    Download a file using wget.
    Uses urllib.request with a progress callback if file size is known.
    """
    try:
        file_size = get_file_size(url)
        filename = os.path.basename(url.split("?")[0]) or "downloaded_file"
        ensure_directory(output_dir)
        output_path = os.path.join(output_dir, filename)

        print_step(f"Downloading: {url}")
        print_step(f"Destination: {output_path}")

        if file_size:
            print_step(f"File size: {format_size(file_size)}")
        else:
            print_warning("File size unknown; progress will be indeterminate.")

        if file_size > 0:
            progress = ProgressBar(file_size, "Downloading")

            def progress_callback(
                block_count: int, block_size: int, total_size: int
            ) -> None:
                progress.update(block_size)

            import urllib.request

            urllib.request.urlretrieve(url, output_path, reporthook=progress_callback)
        else:
            with Spinner(f"Downloading {filename}") as spinner:
                run_command(["wget", "-q", "-O", output_path, url], verbose=verbose)

        if not os.path.exists(output_path):
            print_error("Download failed: Output file not found.")
            return False

        file_stats = os.stat(output_path)
        print_success(f"Downloaded {format_size(file_stats.st_size)} to {output_path}")
        return True
    except Exception as e:
        print_error(f"Download failed: {e}")
        return False


def download_with_yt_dlp(url: str, output_dir: str, verbose: bool = False) -> bool:
    """
    Download a YouTube video using yt-dlp.
    Displays progress by parsing yt-dlp output.
    """
    try:
        ensure_directory(output_dir)
        estimated_size = estimate_youtube_size(url)
        if estimated_size:
            print_step(f"Estimated size: {format_size(estimated_size)}")
        try:
            result = run_command(
                ["yt-dlp", "--print", "title", url], capture_output=True
            )
            video_title = result.stdout.strip() or "Unknown video"
            print_step(f"Video title: {video_title}")
        except Exception:
            video_title = "Unknown video"

        output_template = os.path.join(output_dir, "%(title)s.%(ext)s")
        cmd = [
            "yt-dlp",
            "-f",
            "bestvideo+bestaudio",
            "--merge-output-format",
            "mp4",
            "-o",
            output_template,
        ]
        if verbose:
            cmd.append("--verbose")
        cmd.append(url)

        if verbose:
            with Spinner(f"Downloading {video_title}"):
                run_command(cmd, verbose=True)
        else:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )
            progress: Optional[ProgressBar] = None
            # Parse yt-dlp output for progress information.
            while True:
                line = process.stdout.readline()
                if not line:
                    break
                # Clear current line for smooth update
                console.print("\r" + " " * TERM_WIDTH, end="\r")
                if "[download]" in line and "%" in line:
                    try:
                        pct_str = line.split()[1].rstrip(",").rstrip("%")
                        pct = float(pct_str)
                        if progress is None:
                            progress = ProgressBar(100, "Downloading")
                        progress.current = pct
                        progress._display()
                    except Exception:
                        pass
                elif "Downloading video" in line or "Downloading audio" in line:
                    if progress is not None:
                        progress.desc = line.strip()
                        progress._display()
            process.wait()
            if process.returncode != 0:
                print_error("Download failed.")
                return False

        print_success(f"Successfully downloaded {video_title}")
        return True
    except Exception as e:
        print_error(f"Download failed: {e}")
        return False


# ------------------------------
# Command Functions
# ------------------------------
def cmd_wget(url: str, output_dir: str, verbose: bool) -> None:
    """Execute the wget download command after ensuring dependencies."""
    required = DEPENDENCIES["common"] + DEPENDENCIES["wget"]
    if not check_dependencies(required):
        if os.geteuid() == 0:
            if not install_dependencies(required, verbose):
                print_error("Failed to install dependencies.")
                sys.exit(1)
        else:
            print_error("Missing dependencies and not running as root to install them.")
            sys.exit(1)
    success = download_with_wget(url, output_dir, verbose)
    sys.exit(0 if success else 1)


def cmd_ytdlp(url: str, output_dir: str, verbose: bool) -> None:
    """Execute the yt-dlp download command after ensuring dependencies."""
    required = DEPENDENCIES["common"] + DEPENDENCIES["yt-dlp"]
    if not check_dependencies(required):
        if os.geteuid() == 0:
            if not install_dependencies(required, verbose):
                print_error("Failed to install dependencies.")
                sys.exit(1)
        else:
            print_error("Missing dependencies and not running as root to install them.")
            sys.exit(1)
    success = download_with_yt_dlp(url, output_dir, verbose)
    sys.exit(0 if success else 1)


# ------------------------------
# Interactive Menu Functions
# ------------------------------
def download_menu() -> None:
    """Interactive download menu for the Universal Downloader."""
    print_header("Universal Downloader")
    print_section("Download Options")
    console.print("[#D8DEE9]1. Download a file using wget[/#D8DEE9]")
    console.print("[#D8DEE9]2. Download a YouTube video using yt-dlp[/#D8DEE9]")
    console.print("[#D8DEE9]3. Exit[/#D8DEE9]")

    while True:
        choice = console.input(
            "\n[bold #B48EAD]Enter your choice (1-3): [/bold #B48EAD]"
        ).strip()
        if choice == "1":
            required = DEPENDENCIES["common"] + DEPENDENCIES["wget"]
            if not check_dependencies(required):
                if os.geteuid() == 0:
                    if not install_dependencies(required):
                        print_error("Failed to install dependencies.")
                        return
                else:
                    print_error(
                        "Missing dependencies and not running as root to install them."
                    )
                    return
            url = console.input(
                "\n[bold #B48EAD]Enter URL to download: [/bold #B48EAD]"
            ).strip()
            if not url:
                print_error("URL cannot be empty.")
                return
            output_dir = (
                console.input(
                    f"[bold #B48EAD]Enter output directory [{DEFAULT_DOWNLOAD_DIR}]: [/bold #B48EAD]"
                ).strip()
                or DEFAULT_DOWNLOAD_DIR
            )
            download_with_wget(url, output_dir)
            break
        elif choice == "2":
            required = DEPENDENCIES["common"] + DEPENDENCIES["yt-dlp"]
            if not check_dependencies(required):
                if os.geteuid() == 0:
                    if not install_dependencies(required):
                        print_error("Failed to install dependencies.")
                        return
                else:
                    print_error(
                        "Missing dependencies and not running as root to install them."
                    )
                    return
            url = console.input(
                "\n[bold #B48EAD]Enter YouTube URL: [/bold #B48EAD]"
            ).strip()
            if not url:
                print_error("URL cannot be empty.")
                return
            output_dir = (
                console.input(
                    f"[bold #B48EAD]Enter output directory [{DEFAULT_DOWNLOAD_DIR}]: [/bold #B48EAD]"
                ).strip()
                or DEFAULT_DOWNLOAD_DIR
            )
            download_with_yt_dlp(url, output_dir)
            break
        elif choice == "3":
            print_step("Exiting...")
            return
        else:
            print_error("Invalid selection. Please choose 1-3.")


def parse_args() -> Dict[str, Any]:
    """Parse command-line arguments into a dictionary."""
    args: Dict[str, Any] = {}
    argv = sys.argv[1:]
    if not argv:
        return {"command": "menu"}
    command = argv[0]
    args["command"] = command
    if command in ["wget", "ytdlp"]:
        url = None
        output_dir = DEFAULT_DOWNLOAD_DIR
        verbose = False
        i = 1
        while i < len(argv):
            if argv[i] in ["-o", "--output-dir"] and i + 1 < len(argv):
                output_dir = argv[i + 1]
                i += 2
            elif argv[i] in ["-v", "--verbose"]:
                verbose = True
                i += 1
            elif argv[i].startswith("-"):
                i += 1
                if i < len(argv) and not argv[i].startswith("-"):
                    i += 1
            else:
                url = argv[i]
                i += 1
        args["url"] = url
        args["output_dir"] = output_dir
        args["verbose"] = verbose
    return args


def show_usage() -> None:
    """Display usage information for the script."""
    print_header(f"Universal Downloader v{VERSION}")
    print_section("Usage")
    console.print("[bold #D8DEE9]Universal Downloader Script[/bold #D8DEE9]\n")
    console.print("[#88C0D0]Commands:[/#88C0D0]")
    console.print(
        "  [#D8DEE9]menu                      Start the interactive download menu[/#D8DEE9]"
    )
    console.print(
        "  [#D8DEE9]wget <url> [options]      Download a file using wget[/#D8DEE9]"
    )
    console.print(
        "  [#D8DEE9]ytdlp <url> [options]     Download a YouTube video using yt-dlp[/#D8DEE9]\n"
    )
    console.print("[#88C0D0]Options:[/#88C0D0]")
    console.print(
        "  [#D8DEE9]-o, --output-dir <dir>    Set the output directory (default: ~/Downloads)[/#D8DEE9]"
    )
    console.print(
        "  [#D8DEE9]-v, --verbose             Enable verbose output[/#D8DEE9]\n"
    )
    console.print("[#88C0D0]Examples:[/#88C0D0]")
    console.print("  [#D8DEE9]./universal_downloader.py menu[/#D8DEE9]")
    console.print(
        "  [#D8DEE9]./universal_downloader.py wget https://example.com/file.zip -o /tmp[/#D8DEE9]"
    )
    console.print(
        "  [#D8DEE9]./universal_downloader.py ytdlp https://youtube.com/watch?v=12345 -v[/#D8DEE9]"
    )


# ------------------------------
# Main Entry Point
# ------------------------------
def main() -> None:
    """Main function: parses arguments, checks connectivity, and dispatches commands."""
    try:
        print_header(f"Universal Downloader v{VERSION}")
        console.print(
            f"System: [bold #81A1C1]{platform.system()} {platform.release()}[/bold #81A1C1]"
        )
        console.print(
            f"User: [bold #81A1C1]{os.environ.get('USER', 'unknown')}[/bold #81A1C1]"
        )
        console.print(
            f"Time: [bold #81A1C1]{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/bold #81A1C1]"
        )
        console.print(
            f"Working directory: [bold #81A1C1]{os.getcwd()}[/bold #81A1C1]\n"
        )
        setup_logging()

        if not check_internet_connectivity():
            print_error(
                "No internet connectivity detected. Please check your connection."
            )
            sys.exit(1)

        check_root_privileges()

        args = parse_args()
        command = args.get("command")
        if command == "menu" or command is None:
            download_menu()
        elif command == "wget":
            if not args.get("url"):
                print_error("URL is required for wget command.")
                show_usage()
                sys.exit(1)
            cmd_wget(args["url"], args["output_dir"], args.get("verbose", False))
        elif command == "ytdlp":
            if not args.get("url"):
                print_error("URL is required for ytdlp command.")
                show_usage()
                sys.exit(1)
            cmd_ytdlp(args["url"], args["output_dir"], args.get("verbose", False))
        elif command in ["help", "--help", "-h"]:
            show_usage()
        else:
            print_error(f"Unknown command: {command}")
            show_usage()
            sys.exit(1)
    except KeyboardInterrupt:
        print_warning("\nProcess interrupted by user.")
        sys.exit(130)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
