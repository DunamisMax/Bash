#!/usr/local/bin/bash
# ------------------------------------------------------------------------------
# FreeBSD Automated System Configuration Script
# ------------------------------------------------------------------------------
# Description:
#   Automates the setup and configuration of a fresh FreeBSD system, including:
#     • System updates and package upgrades.
#     • Full system backups with retention policies.
#     • User creation, sudo access, and Bash environment configuration.
#     • Installation of essential development tools, languages, and utilities.
#     • Configuration of SSH with security best practices.
#     • Setup and hardening of the PF firewall.
#     • Download and setup of GitHub repositories.
#     • Installation of Visual Studio Code CLI and FiraCode Nerd Font.
#     • Configuration of dotfiles for a personalized environment.
#     • Directory permission management and cleanup.
#     • Final system checks and logging of system information.
#     • Optional reboot prompt to apply changes.
#
# Usage:
#   • Run as root or via sudo.
#   • Adjust configuration variables (e.g., USERNAME, PACKAGES) as needed.
#   • Logs actions and errors to /var/log/freebsd_setup.log with timestamps.
#
# Error Handling:
#   • Uses 'set -Eeuo pipefail' for strict error handling.
#   • Implements an ERR trap to log errors and provide context.
#   • Custom error handling with detailed messages and exit codes.
#
# Compatibility:
#   • Tested on FreeBSD 14+. Verify compatibility on other versions.
#
# Author: dunamismax | License: MIT
# ------------------------------------------------------------------------------

# Enable strict error handling
set -Eeuo pipefail

# ------------------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------------------
LOG_FILE="/var/log/freebsd_setup.log"  # Path to the log file
VERBOSE=2                              # Verbosity level (0: silent, 1: errors only, 2: info, 3: debug)
USERNAME="sawyer"                      # Default username to configure (change as needed)

# ------------------------------------------------------------------------------
# Initial Checks
# ------------------------------------------------------------------------------

# Ensure the script is run as root
if [[ $(id -u) -ne 0 ]]; then
  handle_error "This script must be run as root (e.g., sudo $0)."
fi

# Ensure the log directory exists and is writable
LOG_DIR=$(dirname "$LOG_FILE")
if [[ ! -d "$LOG_DIR" ]]; then
  mkdir -p "$LOG_DIR" || handle_error "Failed to create log directory: $LOG_DIR"
fi
touch "$LOG_FILE" || handle_error "Failed to create log file: $LOG_FILE"
chmod 600 "$LOG_FILE"  # Restrict log file access to root only

# Validate network connectivity
if ! ping -c 1 google.com &>/dev/null; then
    handle_error "No network connectivity. Please check your network settings."
fi

# ------------------------------------------------------------------------------
# Function: Logging
# ------------------------------------------------------------------------------
log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp
    timestamp=$(date +"%Y-%m-%d %H:%M:%S")

    # Define color codes for terminal output
    local RED='\033[0;31m'
    local YELLOW='\033[0;33m'
    local GREEN='\033[0;32m'
    local BLUE='\033[0;34m'
    local NC='\033[0m'  # No Color

    # Map log levels to colors
    case "${level^^}" in
        INFO)
            local color="${GREEN}"
            ;;
        WARN|WARNING)
            local color="${YELLOW}"
            level="WARN"
            ;;
        ERROR)
            local color="${RED}"
            ;;
        DEBUG)
            local color="${BLUE}"
            ;;
        *)
            local color="${NC}"
            level="INFO"
            ;;
    esac

    # Format the log entry
    local log_entry="[$timestamp] [$level] $message"

    # Append to log file
    echo "$log_entry" >> "$LOG_FILE"

    # Output to console based on verbosity level
    # Verbosity levels:
    # 0: Silent (no output)
    # 1: Errors only
    # 2: Info and errors
    # 3: Debug, info, and errors
    if [[ "$VERBOSE" -ge 2 ]]; then
        printf "${color}%s${NC}\n" "$log_entry" >&2
    elif [[ "$VERBOSE" -ge 1 && "$level" == "ERROR" ]]; then
        printf "${color}%s${NC}\n" "$log_entry" >&2
    fi
}

# ------------------------------------------------------------------------------
# Function: Error Handling
# ------------------------------------------------------------------------------
handle_error() {
    local error_message="${1:-An error occurred. Check the log for details.}"
    local exit_code="${2:-1}"  # Default exit code is 1
    local timestamp
    timestamp=$(date +"%Y-%m-%d %H:%M:%S")

    # Log the error with additional context
    log ERROR "$error_message (Exit Code: $exit_code)"
    log ERROR "Script failed at line $LINENO in function ${FUNCNAME[1]}."

    # Optionally, print the error to stderr for immediate visibility
    echo "ERROR: $error_message (Exit Code: $exit_code)" >&2
    echo "Script failed at line $LINENO in function ${FUNCNAME[1]}." >&2

    # Exit with the specified exit code
    exit "$exit_code"
}

# Trap errors and log them with context
trap 'log ERROR "Script failed in function ${FUNCNAME[0]} at line $LINENO. See above for details."' ERR

# ------------------------------------------------------------------------------
# Function: Perform initial system update and upgrade
# ------------------------------------------------------------------------------
initial_system_update() {
    log INFO "--------------------------------------"
    log INFO "Starting initial system update and upgrade..."

    # Update package repositories
    log INFO "Updating package repositories..."
    if ! pkg update; then
        handle_error "Failed to update package repositories. Check repository configuration."
    fi
    log INFO "Package repositories updated successfully."

    # Upgrade installed packages
    log INFO "Upgrading installed packages..."
    if ! pkg upgrade -y; then
        handle_error "Failed to upgrade installed packages."
    fi
    log INFO "Installed packages upgraded successfully."

    log INFO "Initial system update and upgrade completed successfully."
    log INFO "--------------------------------------"
}

# ------------------------------------------------------------------------------
# Main Functions Begin Here
# ------------------------------------------------------------------------------
# Add FreeBSD-specific functions below (e.g., pkg updates, config overwrites)
# and call them in the "main" block at the end of the script.

# ------------------------------------------------------------------------------
# Function: Perform initial full system backup
# ------------------------------------------------------------------------------
backup_system() {
    log INFO "--------------------------------------"
    log INFO "Starting system backup process..."

    # Install rsync if not already installed
    if ! command -v rsync &>/dev/null; then
        log INFO "Installing rsync..."
        if ! pkg install -y rsync; then
            handle_error "Failed to install rsync. Exiting."
        fi
    fi

    # Verify rsync installation
    if ! command -v rsync &>/dev/null; then
        handle_error "rsync is not installed. Exiting."
    fi

    # Variables
    local SOURCE="/"
    local DESTINATION="/home/${USERNAME}/BACKUPS"
    local TIMESTAMP
    TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
    local BACKUP_FOLDER="$DESTINATION/backup-$TIMESTAMP"
    local RETENTION_DAYS=7
    local EXCLUDES=(
        "/proc/*" "/sys/*" "/dev/*" "/run/*" "/tmp/*" "/mnt/*" "/media/*"
        "/swapfile" "/lost+found" "/var/tmp/*" "/var/cache/*" "/var/log/*"
        "/var/lib/docker/*" "/root/.cache/*" "/home/*/.cache/*" "$DESTINATION"
    )

    # Convert EXCLUDES array into rsync-compatible arguments
    local EXCLUDES_ARGS=()
    for EXCLUDE in "${EXCLUDES[@]}"; do
        EXCLUDES_ARGS+=(--exclude="$EXCLUDE")
    done

    # Create backup destination directory
    if ! mkdir -p "$BACKUP_FOLDER"; then
        handle_error "Failed to create backup directory: $BACKUP_FOLDER"
    fi

    # Perform the backup using rsync
    log INFO "Starting system backup to $BACKUP_FOLDER..."
    if rsync -aAXv --stats "${EXCLUDES_ARGS[@]}" "$SOURCE" "$BACKUP_FOLDER"; then
        log INFO "Backup completed successfully: $BACKUP_FOLDER"
    else
        handle_error "Backup process failed."
    fi

    # Clean up old backups
    log INFO "Cleaning up backups older than $RETENTION_DAYS days..."
    if find "$DESTINATION" -type d -name "backup-*" -mtime +"$RETENTION_DAYS" -exec rm -rf {} +; then
        log INFO "Old backups removed successfully."
    else
        log WARN "Failed to remove some old backups."
    fi

    log INFO "System backup process completed."
    log INFO "--------------------------------------"
}

# ------------------------------------------------------------------------------
# Function: Configure User for Sudo Access
# ------------------------------------------------------------------------------
configure_sudo_access() {
    log INFO "--------------------------------------"
    log INFO "Configuring sudo access for user: $USERNAME"

    # Check if the user exists
    if ! id "$USERNAME" &>/dev/null; then
        handle_error "User $USERNAME does not exist."
    fi

    # Add the user to the 'wheel' group
    log INFO "Adding user $USERNAME to the 'wheel' group..."
    if ! pw usermod "$USERNAME" -G wheel; then
        handle_error "Failed to add user $USERNAME to the 'wheel' group."
    fi

    # Ensure the sudoers file includes the 'wheel' group
    log INFO "Configuring sudoers file for 'wheel' group..."
    if ! grep -q '^%wheel ALL=(ALL) ALL' /usr/local/etc/sudoers; then
        echo "%wheel ALL=(ALL) ALL" >> /usr/local/etc/sudoers || {
            handle_error "Failed to update sudoers file."
        }
        log INFO "Added 'wheel' group to sudoers file."
    else
        log INFO "'wheel' group already configured in sudoers file."
    fi

    log INFO "Sudo access configured successfully for user: $USERNAME"
    log INFO "--------------------------------------"
}

# ------------------------------------------------------------------------------
# Function: Install all packages
# ------------------------------------------------------------------------------
install_pkgs() {
    log INFO "--------------------------------------"
    log INFO "Starting package installation process..."

    # Update pkg repositories and upgrade existing packages
    log INFO "Updating pkg repositories and upgrading packages..."
    if ! pkg upgrade -y; then
        handle_error "Failed to update or upgrade packages. Exiting."
    fi
    log INFO "System upgrade completed successfully."

    # Define packages to install
    PACKAGES=(
        # Development tools
        gcc cmake git pkgconf openssl llvm autoconf automake libtool ninja meson gettext
        gmake valgrind doxygen ccache diffutils alacritty node npm

        # Scripting and utilities
        bash zsh fish nano screen tmate mosh htop iftop
        tree wget curl rsync unzip zip ca_root_nss sudo less neovim mc jq pigz fzf lynx
        smartmontools neofetch screenfetch ncdu dos2unix figlet toilet ripgrep

        # Libraries for Python & C/C++ build
        libffi readline sqlite3 ncurses gdbm nss lzma libxml2

        # Networking, system admin, and hacking utilities
        nmap netcat socat tcpdump wireshark aircrack-ng john hydra openvpn ipmitool bmon whois bind-tools

        # Languages and runtimes
        python39 go ruby perl5 rust

        # Containers and virtualization
        docker vagrant qemu

        # Web hosting tools
        nginx postgresql15-server postgresql15-client

        # File and backup management
        rclone

        # System monitoring and logging
        syslog-ng grafana prometheus netdata

        # Miscellaneous tools
        lsof bsdstats
    )

    # Install packages
    log INFO "Installing pkg-based build dependencies and popular packages..."
    if ! pkg install -y "${PACKAGES[@]}"; then
        handle_error "Failed to install one or more packages. Exiting."
    fi
    log INFO "All packages installed successfully."

    # Verify critical packages are installed
    local CRITICAL_PACKAGES=("bash" "sudo" "openssl" "python39" "git")
    for pkg in "${CRITICAL_PACKAGES[@]}"; do
        if ! pkg info -q "$pkg"; then
            handle_error "Critical package $pkg is missing. Exiting."
        fi
    done
    log INFO "Verified critical packages are installed."

    log INFO "Package installation process completed."
    log INFO "--------------------------------------"
}

configure_ssh_settings() {
    local sshd_config="/usr/local/etc/ssh/sshd_config"
    local sshd_service="sshd"
    local pkg_name="openssh-portable"
    local TIMEOUT=30
    local retry_count=0
    local max_retries=3

    # Ensure clean environment
    export LC_ALL=C

    log INFO "--------------------------------------"
    log INFO "Starting SSH server configuration..."

    # Install OpenSSH server with retry logic
    if ! pkg info "${pkg_name}" >/dev/null 2>&1; then
        while [ ${retry_count} -lt ${max_retries} ]; do
            log INFO "Installing OpenSSH Server (attempt $((retry_count + 1))/${max_retries})..."
            if pkg install -y "${pkg_name}"; then
                break
            fi
            retry_count=$((retry_count + 1))
            [ ${retry_count} -lt ${max_retries} ] && sleep 5
        done

        if [ ${retry_count} -eq ${max_retries} ]; then
            handle_error "Failed to install OpenSSH Server after ${max_retries} attempts."
        fi
    else
        log INFO "OpenSSH Server is already installed."
    fi

    # Create SSH directory if it doesn't exist
    if [ ! -d "/usr/local/etc/ssh" ]; then
        if ! mkdir -p "/usr/local/etc/ssh"; then
            handle_error "Failed to create SSH configuration directory."
        fi
        chmod 755 "/usr/local/etc/ssh"
    fi

    # Backup existing configuration if it exists
    if [ -f "${sshd_config}" ]; then
        local backup_file="${sshd_config}.bak.$(date +%Y%m%d%H%M%S)"
        if ! cp "${sshd_config}" "${backup_file}"; then
            handle_error "Failed to create backup of sshd_config."
        fi
        log INFO "Created backup of sshd_config at ${backup_file}"
    fi

    # Generate new sshd_config with security best practices
    log INFO "Generating new SSH configuration..."

    # Create a temporary file using mktemp
    local temp_file
    temp_file=$(mktemp) || handle_error "Failed to create temporary file for SSH configuration."

    {
        printf "# SSH Server Configuration - Generated on %s\n\n" "$(date)"
        printf "# Network settings\n"
        printf "Port 22\n"
        printf "Protocol 2\n"
        printf "AddressFamily inet\n"  # Restrict to IPv4
        printf "ListenAddress 0.0.0.0\n\n"
        
        printf "# Authentication settings\n"
        printf "MaxAuthTries 3\n"
        printf "PermitRootLogin no\n"
        printf "PasswordAuthentication yes\n"
        printf "ChallengeResponseAuthentication no\n"
        printf "UsePAM no\n"
        printf "PubkeyAuthentication yes\n"
        printf "AuthenticationMethods publickey\n\n"
        
        printf "# Security settings\n"
        printf "X11Forwarding no\n"
        printf "AllowTcpForwarding no\n"
        printf "PermitEmptyPasswords no\n"
        printf "MaxSessions 2\n"
        printf "LoginGraceTime 30\n"
        printf "AllowAgentForwarding no\n"
        printf "PermitTunnel no\n"
        printf "StrictModes yes\n\n"
        
        printf "# Connection settings\n"
        printf "ClientAliveInterval 300\n"
        printf "ClientAliveCountMax 2\n"
        printf "TCPKeepAlive no\n\n"  # Disable TCP keepalive to prevent connection hijacking
        
        printf "# Logging settings\n"
        printf "LogLevel VERBOSE\n"
        printf "SyslogFacility AUTH\n"
    } > "${temp_file}"

    # Verify the temporary config file was created
    if [ ! -f "${temp_file}" ]; then
        handle_error "Failed to create new SSH configuration."
    fi

    # Set proper permissions on the temporary config file
    if ! chmod 600 "${temp_file}"; then
        handle_error "Failed to set permissions on new SSH configuration."
    fi

    # Move temporary config to final location
    if ! mv "${temp_file}" "${sshd_config}"; then
        handle_error "Failed to move new SSH configuration to final location."
    fi

    # Enable sshd in rc.conf using sysrc
    log INFO "Enabling SSH service..."
    if ! sysrc "${sshd_service}_enable=YES" >/dev/null 2>&1; then
        handle_error "Failed to enable SSH service in rc.conf."
    fi

    # Test configuration before applying
    log INFO "Testing SSH configuration..."
    if ! /usr/sbin/sshd -t -f "${sshd_config}"; then
        handle_error "SSH configuration test failed."
    fi

    # Restart sshd service
    log INFO "Restarting SSH service..."
    if ! service "${sshd_service}" restart >/dev/null 2>&1; then
        handle_error "Failed to restart SSH service."
    fi

    # Verify service is running
    retry_count=0
    while [ ${retry_count} -lt ${TIMEOUT} ]; do
        if service "${sshd_service}" status >/dev/null 2>&1; then
            # Verify SSH is listening
            if sockstat -4l | grep -q ":22"; then
                log INFO "SSH server is running and listening on port 22."
                break
            fi
        fi
        retry_count=$((retry_count + 1))
        sleep 1
    done

    if [ ${retry_count} -eq ${TIMEOUT} ]; then
        handle_error "SSH service failed to start properly within ${TIMEOUT} seconds."
    fi

    log INFO "SSH server configuration completed successfully."
    log INFO "--------------------------------------"
    return 0
}

# ------------------------------------------------------------------------------
# Function: Configure PF Firewall
# ------------------------------------------------------------------------------
configure_pf() {
    log INFO "--------------------------------------"
    log INFO "Starting PF firewall configuration..."

    # Configuration paths
    local PF_CONF="/etc/pf.conf"
    local BACKUP_CONF="/etc/pf.conf.bak.$(date +%Y%m%d%H%M%S)"

    # Backup existing PF configuration
    if [[ -f "$PF_CONF" ]]; then
        log INFO "Backing up existing PF configuration to $BACKUP_CONF..."
        if ! cp "$PF_CONF" "$BACKUP_CONF"; then
            handle_error "Failed to back up PF configuration."
        fi
        log INFO "Existing PF configuration backed up to $BACKUP_CONF."
    fi

    # Detect the active network interface
    log INFO "Detecting active network interface..."
    local INTERFACE
    INTERFACE=$(route -n get default | awk '/interface:/ {print $2}')
    if [[ -z "$INTERFACE" ]]; then
        handle_error "Unable to detect the active network interface. Exiting."
    fi
    log INFO "Detected active network interface: $INTERFACE"

    # Define PF rules using the detected interface
    log INFO "Generating new PF configuration..."
    cat <<EOF > "$PF_CONF"
# PF configuration generated by configure_pf script

# Define network interface
ext_if = "$INTERFACE"

# Default block policy
set block-policy drop
block all

# Allow loopback
pass quick on lo0 all

# Allow established connections
pass out quick inet proto { tcp udp } from any to any keep state

# SSH
pass in quick on \$ext_if proto tcp to (\$ext_if) port 22 keep state

# HTTP/HTTPS
pass in quick on \$ext_if proto tcp to (\$ext_if) port { 80 443 } keep state

# Custom application ports (adjust as needed)
pass in quick on \$ext_if proto tcp to (\$ext_if) port { 8080, 32400, 8324, 32469 } keep state
pass in quick on \$ext_if proto udp to (\$ext_if) port { 1900, 5353, 32410, 32411, 32412, 32413, 32414, 32415 } keep state

# Additional default allow for outbound traffic
pass out all keep state
EOF

    # Verify the new configuration file was created
    if [[ ! -f "$PF_CONF" ]]; then
        handle_error "Failed to create new PF configuration file."
    fi

    # Ensure PF kernel module is loaded
    if ! kldstat | grep -q pf; then
        log INFO "Loading PF kernel module..."
        if ! kldload pf; then
            handle_error "Failed to load PF kernel module."
        fi
        echo 'pf_load="YES"' >> /boot/loader.conf
        log INFO "PF kernel module will load on boot."
    else
        log INFO "PF kernel module is already loaded."
    fi

    # Enable PF in rc.conf
    if ! grep -q '^pf_enable="YES"' /etc/rc.conf; then
        log INFO "Enabling PF in /etc/rc.conf..."
        if ! sysrc pf_enable="YES"; then
            handle_error "Failed to enable PF in /etc/rc.conf."
        fi
        log INFO "PF enabled in /etc/rc.conf."
    else
        log INFO "PF is already enabled in /etc/rc.conf."
    fi

    # Check for /dev/pf
    if [[ ! -c /dev/pf ]]; then
        handle_error "/dev/pf missing. Ensure PF kernel module is loaded."
    fi

    # Load PF configuration
    log INFO "Loading PF configuration..."
    if ! pfctl -nf "$PF_CONF"; then
        handle_error "Failed to validate PF configuration."
    fi
    if ! pfctl -f "$PF_CONF"; then
        handle_error "Failed to load PF configuration."
    fi
    log INFO "PF configuration loaded successfully."

    # Enable PF if not already active
    if pfctl -s info | grep -q "Status: Enabled"; then
        log INFO "PF is already active."
    else
        log INFO "Enabling PF..."
        if ! pfctl -e; then
            handle_error "Failed to enable PF."
        fi
        log INFO "PF enabled."
    fi

    log INFO "PF firewall configuration completed successfully."
    log INFO "--------------------------------------"
}

# ------------------------------------------------------------------------------
# Function: Install VSCode CLI
# ------------------------------------------------------------------------------
install_vscode_cli() {
    log INFO "--------------------------------------"
    log INFO "Starting Visual Studio Code CLI installation..."

    # Ensure Node.js is installed
    if ! command -v node &>/dev/null; then
        handle_error "Node.js is not installed. Please install Node.js before proceeding."
    fi

    # Create a symbolic link for Node.js
    log INFO "Creating symbolic link for Node.js..."
    local node_bin
    node_bin=$(which node)
    if [[ -z "$node_bin" ]]; then
        handle_error "Node.js binary not found. Exiting."
    fi

    if [[ -e "/usr/local/node" || -L "/usr/local/node" ]]; then
        log INFO "Removing existing symbolic link or file at /usr/local/node..."
        rm -f "/usr/local/node" || {
            handle_error "Failed to remove existing symbolic link or file at /usr/local/node."
        }
    fi

    if ln -s "$node_bin" /usr/local/node; then
        log INFO "Symbolic link created at /usr/local/node."
    else
        handle_error "Failed to create symbolic link for Node.js."
    fi

    # Download Visual Studio Code CLI
    log INFO "Downloading Visual Studio Code CLI..."
    local vscode_cli_url="https://code.visualstudio.com/sha/download?build=stable&os=cli-alpine-x64"
    local vscode_cli_tarball="vscode_cli.tar.gz"

    if ! curl -Lk "$vscode_cli_url" --output "$vscode_cli_tarball"; then
        handle_error "Failed to download Visual Studio Code CLI."
    fi
    log INFO "Downloaded $vscode_cli_tarball successfully."

    # Extract the tarball
    log INFO "Extracting $vscode_cli_tarball..."
    if ! tar -xf "$vscode_cli_tarball"; then
        handle_error "Failed to extract $vscode_cli_tarball."
    fi
    log INFO "Extraction completed successfully."

    # Clean up the tarball
    log INFO "Cleaning up temporary files..."
    rm -f "$vscode_cli_tarball" || {
        log WARN "Failed to remove $vscode_cli_tarball. Manual cleanup may be required."
    }

    # Verify the extracted binary
    if [[ ! -f "./code" ]]; then
        handle_error "Failed to locate the 'code' binary after extraction."
    fi

    # Set executable permissions
    log INFO "Setting executable permissions for the 'code' binary..."
    chmod +x ./code || {
        handle_error "Failed to set executable permissions for the 'code' binary."
    }

    log INFO "Visual Studio Code CLI installation completed successfully."
    log INFO "Run './code tunnel --name freebsd-server' from the current directory to start the tunnel."
    log INFO "--------------------------------------"
}

# ------------------------------------------------------------------------------
# Function: Install FiraCode Nerd Font
# ------------------------------------------------------------------------------
install_font() {
    local font_url="https://github.com/ryanoasis/nerd-fonts/raw/master/patched-fonts/FiraCode/Regular/FiraCodeNerdFont-Regular.ttf"
    local font_dir="/usr/local/share/fonts/nerd-fonts"
    local font_file="FiraCodeNerdFont-Regular.ttf"

    log INFO "--------------------------------------"
    log INFO "Starting FiraCode Nerd Font installation..."

    # Create the font directory if it doesn't exist
    if [[ ! -d "$font_dir" ]]; then
        log INFO "Creating font directory: $font_dir"
        if ! mkdir -p "$font_dir"; then
            handle_error "Failed to create font directory: $font_dir"
        fi
    fi

    # Download the font
    log INFO "Downloading font from $font_url..."
    if ! fetch -o "$font_dir/$font_file" "$font_url"; then
        handle_error "Failed to download font from $font_url."
    fi
    log INFO "Font downloaded successfully."

    # Verify the font file was downloaded
    if [[ ! -f "$font_dir/$font_file" ]]; then
        handle_error "Font file not found after download: $font_dir/$font_file"
    fi

    # Set appropriate permissions for the font file
    log INFO "Setting permissions for the font file..."
    if ! chmod 644 "$font_dir/$font_file"; then
        handle_error "Failed to set permissions for the font file."
    fi

    # Refresh the font cache
    log INFO "Refreshing font cache..."
    if ! fc-cache -fv >/dev/null 2>&1; then
        handle_error "Failed to refresh font cache."
    fi
    log INFO "Font cache refreshed successfully."

    # Verify the font is available in the system
    log INFO "Verifying font installation..."
    if ! fc-list | grep -q "FiraCode Nerd Font"; then
        handle_error "Font verification failed. FiraCode Nerd Font is not available in the system."
    fi

    log INFO "FiraCode Nerd Font installation completed successfully."
    log INFO "--------------------------------------"
    return 0
}

# ------------------------------------------------------------------------------
# Function: Download git repositories to Home folder
# ------------------------------------------------------------------------------
download_repositories() {
    log INFO "--------------------------------------"
    log INFO "Starting GitHub repositories download..."

    local github_dir="/home/${USERNAME}/github"
    log INFO "Creating GitHub directory at $github_dir"
    if ! mkdir -p "$github_dir"; then
        handle_error "Failed to create GitHub directory: $github_dir"
    fi

    log INFO "Changing to GitHub directory"
    if ! cd "$github_dir"; then
        handle_error "Failed to change to GitHub directory: $github_dir"
    fi

    # List of repositories to clone
    local repos=(
        "bash" "c" "religion" "windows" "hugo" "python"
    )

    # Clone or update repositories
    for repo in "${repos[@]}"; do
        local repo_url="https://github.com/dunamismax/${repo}.git"
        local repo_dir="${github_dir}/${repo}"

        if [[ -d "$repo_dir" ]]; then
            log INFO "Updating existing repository: $repo"
            if ! git -C "$repo_dir" pull; then
                handle_error "Failed to update repository: $repo"
            fi
        else
            log INFO "Cloning repository: $repo"
            if ! git clone "$repo_url" "$repo_dir"; then
                handle_error "Failed to clone repository: $repo"
            fi
        fi
    done

    log INFO "GitHub repositories download completed."

    # Set permissions and ownership for Hugo directories
    log INFO "Setting ownership and permissions for Hugo public directory..."
    local hugo_public_dir="${github_dir}/hugo/dunamismax.com/public"
    if [[ -d "$hugo_public_dir" ]]; then
        if ! chown -R www:www "$hugo_public_dir"; then
            handle_error "Failed to set ownership for Hugo public directory."
        fi
        if ! chmod -R 755 "$hugo_public_dir"; then
            handle_error "Failed to set permissions for Hugo public directory."
        fi
    else
        log WARN "Hugo public directory not found: $hugo_public_dir"
    fi

    log INFO "Setting ownership and permissions for Hugo directory..."
    local hugo_dir="${github_dir}/hugo"
    if [[ -d "$hugo_dir" ]]; then
        if ! chown -R "${USERNAME}:${USERNAME}" "$hugo_dir"; then
            handle_error "Failed to set ownership for Hugo directory."
        fi
        if ! chmod o+rx "/home/${USERNAME}/" "$github_dir" "$hugo_dir" "${hugo_dir}/dunamismax.com"; then
            handle_error "Failed to set permissions for Hugo directory."
        fi
    else
        log WARN "Hugo directory not found: $hugo_dir"
    fi

    # Set ownership for other repositories
    for repo in bash c python religion windows; do
        local repo_dir="${github_dir}/${repo}"
        if [[ -d "$repo_dir" ]]; then
            log INFO "Setting ownership for repository: $repo"
            if ! chown -R "${USERNAME}:${USERNAME}" "$repo_dir"; then
                handle_error "Failed to set ownership for repository: $repo"
            fi
        else
            log WARN "Repository directory not found: $repo_dir"
        fi
    done

    log INFO "Repository download and permissions update completed."
    log INFO "--------------------------------------"
    cd ~ || handle_error "Failed to return to home directory."
}

# ------------------------------------------------------------------------------
# Function: Set directory permissions
# ------------------------------------------------------------------------------
set_directory_permissions() {
    # Configuration
    local GITHUB_DIR="/home/${USERNAME}/github"
    local HUGO_PUBLIC_DIR="${GITHUB_DIR}/hugo/dunamismax.com/public"
    local HUGO_DIR="${GITHUB_DIR}/hugo"
    local HOME="/home/${USERNAME}"
    local BASE_DIR="$GITHUB_DIR"

    # Permissions
    local DIR_PERMISSIONS="700"  # For .git directories
    local FILE_PERMISSIONS="600" # For .git files

    log INFO "--------------------------------------"
    log INFO "Starting directory permission updates..."

    # 1. Make all .sh files executable under GITHUB_DIR
    log INFO "Making all .sh files executable under $GITHUB_DIR"
    if ! find "$GITHUB_DIR" -type f -name "*.sh" -exec chmod +x {} +; then
        handle_error "Failed to set executable permissions for .sh files."
    fi

    # 2. Set ownership for directories
    log INFO "Setting ownership for $GITHUB_DIR and $HOME"
    if ! chown -R "${USERNAME}:${USERNAME}" "$GITHUB_DIR" "$HOME"; then
        handle_error "Failed to set ownership for directories."
    fi

    # 3. Set ownership and permissions for Hugo public directory
    if [[ -d "$HUGO_PUBLIC_DIR" ]]; then
        log INFO "Setting ownership and permissions for Hugo public directory"
        if ! chown -R www:www "$HUGO_PUBLIC_DIR"; then
            handle_error "Failed to set ownership for Hugo public directory."
        fi
        if ! chmod -R 755 "$HUGO_PUBLIC_DIR"; then
            handle_error "Failed to set permissions for Hugo public directory."
        fi
    else
        log WARN "Hugo public directory not found: $HUGO_PUBLIC_DIR"
    fi

    # 4. Set ownership and permissions for Hugo directory and related paths
    if [[ -d "$HUGO_DIR" ]]; then
        log INFO "Setting ownership and permissions for Hugo directory"
        if ! chown -R "${USERNAME}:${USERNAME}" "$HUGO_DIR"; then
            handle_error "Failed to set ownership for Hugo directory."
        fi
        if ! chmod o+rx "$HOME" "$GITHUB_DIR" "$HUGO_DIR" "${HUGO_DIR}/dunamismax.com"; then
            handle_error "Failed to set permissions for Hugo directory."
        fi
    else
        log WARN "Hugo directory not found: $HUGO_DIR"
    fi

    # 5. Ensure BASE_DIR exists
    if [[ ! -d "$BASE_DIR" ]]; then
        handle_error "Base directory does not exist: $BASE_DIR"
    fi

    # 6. Find and fix .git directory permissions
    log INFO "Fixing .git directory permissions in $BASE_DIR..."
    while IFS= read -r -d '' git_dir; do
        if [[ -d "$git_dir" ]]; then
            log INFO "Setting stricter permissions for $git_dir"
            if ! chmod "$DIR_PERMISSIONS" "$git_dir"; then
                handle_error "Failed to set permissions for $git_dir"
            fi
            if ! find "$git_dir" -type d -exec chmod "$DIR_PERMISSIONS" {} +; then
                handle_error "Failed to set directory permissions for $git_dir"
            fi
            if ! find "$git_dir" -type f -exec chmod "$FILE_PERMISSIONS" {} +; then
                handle_error "Failed to set file permissions for $git_dir"
            fi
        else
            log WARN ".git directory not found: $git_dir"
        fi
    done < <(find "$BASE_DIR" -type d -name ".git" -print0)

    log INFO "Directory permission updates completed successfully."
    log INFO "--------------------------------------"
}

# ------------------------------------------------------------------------------
# Function: Load dotfiles
# ------------------------------------------------------------------------------
setup_dotfiles() {
    log INFO "--------------------------------------"
    log INFO "Starting dotfiles setup..."

    # Base paths
    local user_home="/home/${USERNAME}"
    local dotfiles_dir="${user_home}/github/bash/dotfiles"
    local config_dir="${user_home}/.config"
    local local_dir="${user_home}/.local"
    
    # Verify source directory exists
    if [[ ! -d "$dotfiles_dir" ]]; then
        handle_error "Dotfiles directory not found: $dotfiles_dir"
    fi

    # Create necessary directories
    log INFO "Creating required directories..."
    if ! mkdir -p "$config_dir" "$local_dir/bin"; then
        handle_error "Failed to create config directories."
    fi

    # Define files to copy (source:destination)
    local files=(
        "${dotfiles_dir}/.bash_profile:${user_home}/"
        "${dotfiles_dir}/.bashrc:${user_home}/"
        "${dotfiles_dir}/.profile:${user_home}/"
    )

    # Define directories to copy (source:destination)
    local dirs=(
        "${dotfiles_dir}/bin:${local_dir}"
        "${dotfiles_dir}/alacritty:${config_dir}"
    )

    # Copy files
    log INFO "Copying files..."
    for item in "${files[@]}"; do
        local src="${item%:*}"
        local dst="${item#*:}"
        if [[ -f "$src" ]]; then
            if ! cp "$src" "$dst"; then
                handle_error "Failed to copy file: $src"
            fi
            log INFO "Copied file: $src -> $dst"
        else
            log WARN "Source file not found: $src"
        fi
    done

    # Copy directories
    log INFO "Copying directories..."
    for item in "${dirs[@]}"; do
        local src="${item%:*}"
        local dst="${item#*:}"
        if [[ -d "$src" ]]; then
            if ! cp -r "$src" "$dst"; then
                handle_error "Failed to copy directory: $src"
            fi
            log INFO "Copied directory: $src -> $dst"
        else
            log WARN "Source directory not found: $src"
        fi
    done

    # Set ownership and permissions
    log INFO "Setting ownership and permissions..."
    if ! chown -R "${USERNAME}:${USERNAME}" "$user_home"; then
        handle_error "Failed to set ownership for $user_home."
    fi
    if ! chown "${USERNAME}:${USERNAME}" "/usr/local/etc/Caddyfile" 2>/dev/null; then
        log WARN "Failed to set ownership for /usr/local/etc/Caddyfile."
    fi

    log INFO "Dotfiles setup completed successfully."
    log INFO "--------------------------------------"
    return 0
}

# ------------------------------------------------------------------------------
# Function: Finalize system configuration
# ------------------------------------------------------------------------------
finalize_configuration() {
    log INFO "--------------------------------------"
    log INFO "Finalizing system configuration..."

    # Change to the user's home directory
    if ! cd "/home/${USERNAME}"; then
        handle_error "Failed to change to user home directory: /home/${USERNAME}"
    fi

    # Upgrade installed packages using pkg
    log INFO "Upgrading installed packages..."
    if pkg upgrade -y; then
        log INFO "Packages upgraded successfully."
    else
        handle_error "Package upgrade failed."
    fi

    # ------------------------------------------------------------------------------
    # Additional System Logging Information
    # ------------------------------------------------------------------------------
    log INFO "--------------------------------------"
    log INFO "Collecting system information..."
    log INFO "--------------------------------------"

    # Uptime
    log INFO "--------------------------------------"
    log INFO "System Uptime: $(uptime)"
    log INFO "--------------------------------------"

    # Disk usage for root
    log INFO "--------------------------------------"
    log INFO "Disk Usage (root): $(df -h / | tail -1)"
    log INFO "--------------------------------------"

    # Memory usage (FreeBSD equivalent)
    log INFO "--------------------------------------"
    log INFO "Memory and Swap Usage:"
    vmstat -s
    log INFO "--------------------------------------"

    # CPU information
    local CPU_MODEL
    CPU_MODEL=$(sysctl -n hw.model 2>/dev/null || echo "Unknown")
    log INFO "--------------------------------------"
    log INFO "CPU Model: ${CPU_MODEL}"
    log INFO "--------------------------------------"

    # Kernel version
    log INFO "--------------------------------------"
    log INFO "Kernel Version: $(uname -r)"
    log INFO "--------------------------------------"

    # Network configuration
    log INFO "--------------------------------------"
    log INFO "Network Configuration:"
    ifconfig -a
    log INFO "--------------------------------------"

    # End of system information collection
    log INFO "--------------------------------------"
    log INFO "System information logged."
    log INFO "--------------------------------------"

    log INFO "System configuration finalized successfully."
    log INFO "--------------------------------------"
}

# ------------------------------------------------------------------------------
# MAIN
# ------------------------------------------------------------------------------
main() {
    log INFO "--------------------------------------"
    log INFO "Starting FreeBSD Automated System Configuration Script"

    # Bash script execution order
    local functions=(
        backup_system
        configure_sudo_access
        install_pkgs
        configure_ssh_settings
        configure_pf
        download_repositories
        set_directory_permissions
        install_vscode_cli
        install_font
        setup_dotfiles
        finalize_configuration
    )

    # Execute each function in order
    for func in "${functions[@]}"; do
        log INFO "Running function: $func"
        if ! $func; then
            handle_error "Function $func failed."
        fi
    done

    log INFO "Configuration script finished successfully."
    log INFO "Enjoy FreeBSD!"
    log INFO "--------------------------------------"
}

# ------------------------------------------------------------------------------
# Reboot Prompt
# ------------------------------------------------------------------------------
prompt_reboot() {
    log INFO "Setup complete. A reboot is recommended to apply all changes."
    read -p "Reboot now? (y/n): " REBOOT
    if [[ "$REBOOT" == "y" || "$REBOOT" == "Y" ]]; then
        log INFO "Rebooting the system..."
        reboot
    else
        log INFO "Reboot skipped. Please reboot manually when convenient."
    fi
}

# ------------------------------------------------------------------------------
# Entrypoint
# ------------------------------------------------------------------------------
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    # Run the main function
    main "$@"

    # Prompt for reboot after successful completion
    prompt_reboot
fi