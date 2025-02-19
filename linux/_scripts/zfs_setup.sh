#!/usr/bin/env bash
# ------------------------------------------------------------------------------
# Script Name: install_configure_zfs.sh
# Description: A robust script to install and configure ZFS on Debian,
#              using the Nord color theme with detailed logging, strict
#              error handling, and graceful signal traps.
# Author: YourName | License: MIT | Version: 1.0
# ------------------------------------------------------------------------------
#
# Usage:
#   sudo ./install_configure_zfs.sh
#
# Notes:
#   - This script requires root privileges.
#   - Logs are stored at /var/log/ultimate_script.log by default.
#
# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
# ENABLE STRICT MODE & SET IFS
# ------------------------------------------------------------------------------
set -Eeuo pipefail
IFS=$'\n\t'

# ------------------------------------------------------------------------------
# GLOBAL VARIABLES & CONFIGURATION
# ------------------------------------------------------------------------------
readonly LOG_FILE="/var/log/ultimate_script.log"  # Log file path
readonly DISABLE_COLORS="${DISABLE_COLORS:-false}"  # Set to true to disable colored output

# ------------------------------------------------------------------------------
# NORD COLOR THEME CONSTANTS (24-bit ANSI escape sequences)
# ------------------------------------------------------------------------------
readonly NORD9='\033[38;2;129;161;193m'   # #81A1C1 (Bluish)
readonly NORD10='\033[38;2;94;129;172m'   # #5E81AC
readonly NORD11='\033[38;2;191;97;106m'   # #BF616A (Reddish)
readonly NORD13='\033[38;2;235;203;139m'  # #EBCB8B (Yellowish)
readonly NORD14='\033[38;2;163;190;140m'  # #A3BE8C (Greenish)
readonly NC='\033[0m'                     # No Color

# ------------------------------------------------------------------------------
# LOGGING FUNCTION
# ------------------------------------------------------------------------------
log() {
    # Usage: log [LEVEL] message
    local level="${1:-INFO}"
    shift
    local message="$*"
    local upper_level="${level^^}"
    local color="${NC}"

    if [[ "$DISABLE_COLORS" != true ]]; then
        case "$upper_level" in
            INFO)  color="${NORD14}" ;;  # Greenish
            WARN)  color="${NORD13}" ;;  # Yellowish
            ERROR) color="${NORD11}" ;;  # Reddish
            DEBUG) color="${NORD9}"  ;;  # Bluish
            *)     color="${NC}"   ;;
        esac
    fi

    local timestamp
    timestamp="$(date +"%Y-%m-%d %H:%M:%S")"
    local log_entry="[$timestamp] [$upper_level] $message"

    # Append log entry to log file
    echo "$log_entry" >> "$LOG_FILE"
    # Output colored log entry to stderr
    printf "%b%s%b\n" "$color" "$log_entry" "$NC" >&2
}

# ------------------------------------------------------------------------------
# ERROR HANDLING & CLEANUP FUNCTIONS
# ------------------------------------------------------------------------------
handle_error() {
    local error_message="${1:-"An unknown error occurred"}"
    local exit_code="${2:-1}"
    local lineno="${BASH_LINENO[0]:-${LINENO}}"
    local func="${FUNCNAME[1]:-main}"

    log ERROR "$error_message (Exit Code: $exit_code)"
    log ERROR "Error in function '$func' at line $lineno."
    echo -e "${NORD11}ERROR: $error_message (Exit Code: $exit_code)${NC}" >&2
    exit "$exit_code"
}

cleanup() {
    log INFO "Performing cleanup tasks before exit."
    # Insert any necessary cleanup tasks here (e.g., removing temporary files)
}

# Trap EXIT for cleanup and signals for graceful error handling
trap cleanup EXIT
trap 'handle_error "Script interrupted by user." 130' SIGINT
trap 'handle_error "Script terminated." 143' SIGTERM
trap 'handle_error "An unexpected error occurred at line ${BASH_LINENO[0]:-${LINENO}}." "$?"' ERR

# ------------------------------------------------------------------------------
# HELPER & UTILITY FUNCTIONS
# ------------------------------------------------------------------------------
check_root() {
    if [[ "$(id -u)" -ne 0 ]]; then
        handle_error "This script must be run as root."
    fi
}

# Prints a styled section header using Nord accent colors
print_section() {
    local title="$1"
    local border
    border=$(printf '─%.0s' {1..60})
    log INFO "${NORD10}${border}${NC}"
    log INFO "${NORD10}  $title${NC}"
    log INFO "${NORD10}${border}${NC}"
}

# ------------------------------------------------------------------------------
# MAIN LOGIC FUNCTIONS
# ------------------------------------------------------------------------------
install_configure_zfs() {
    print_section "Installing and Configuring ZFS"

    local ZPOOL_NAME="WD_BLACK"
    local MOUNT_POINT="/media/${ZPOOL_NAME}"

    log INFO "Updating package lists..."
    if ! apt update; then
        log ERROR "Failed to update package lists."
        return 1
    fi

    log INFO "Installing prerequisites for ZFS..."
    if ! apt install -y dpkg-dev linux-headers-generic linux-image-generic; then
        log ERROR "Failed to install prerequisites."
        return 1
    fi

    log INFO "Installing ZFS packages..."
    if ! DEBIAN_FRONTEND=noninteractive apt install -y zfs-dkms zfsutils-linux; then
        log ERROR "Failed to install ZFS packages."
        return 1
    fi
    log INFO "ZFS packages installed successfully."

    log INFO "Enabling ZFS auto-import and mount services..."
    systemctl enable zfs-import-cache.service || log WARN "Could not enable zfs-import-cache.service."
    systemctl enable zfs-mount.service || log WARN "Could not enable zfs-mount.service."

    if ! zpool list "$ZPOOL_NAME" >/dev/null 2>&1; then
        log INFO "Importing ZFS pool '$ZPOOL_NAME'..."
        if ! zpool import -f "$ZPOOL_NAME"; then
            log ERROR "Failed to import ZFS pool '$ZPOOL_NAME'."
            return 1
        fi
    else
        log INFO "ZFS pool '$ZPOOL_NAME' is already imported."
    fi

    log INFO "Setting mountpoint for ZFS pool '$ZPOOL_NAME' to '$MOUNT_POINT'..."
    if ! zfs set mountpoint="${MOUNT_POINT}" "$ZPOOL_NAME"; then
        log WARN "Failed to set mountpoint for ZFS pool '$ZPOOL_NAME'."
    else
        log INFO "Mountpoint for pool '$ZPOOL_NAME' successfully set to '$MOUNT_POINT'."
    fi

    log INFO "ZFS installation and configuration finished successfully."
}

# ------------------------------------------------------------------------------
# MAIN ENTRY POINT
# ------------------------------------------------------------------------------
main() {
    # Ensure the script is run with Bash
    if [[ -z "${BASH_VERSION:-}" ]]; then
        echo -e "${NORD11}ERROR: Please run this script with Bash.${NC}" >&2
        exit 1
    fi

    check_root

    # Ensure log directory exists; create if missing
    local log_dir
    log_dir="$(dirname "$LOG_FILE")"
    if [[ ! -d "$log_dir" ]]; then
        mkdir -p "$log_dir" || handle_error "Failed to create log directory: $log_dir"
    fi

    # Ensure the log file exists and set secure permissions
    touch "$LOG_FILE" || handle_error "Failed to create log file: $LOG_FILE"
    chmod 600 "$LOG_FILE" || handle_error "Failed to set permissions on $LOG_FILE"

    log INFO "Script execution started."

    # Execute the ZFS installation and configuration function
    install_configure_zfs

    log INFO "Script execution finished successfully."
}

# Invoke main() if this script is executed directly
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    main "$@"
fi