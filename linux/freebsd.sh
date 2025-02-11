#!/usr/bin/env sh
################################################################################
# FreeBSD Automated Setup & Hardening Script (Improved Version)
################################################################################

# Exit immediately if a command fails or if an undefined variable is used.
set -eu

# ------------------------------------------------------------------------------
# 1. CONFIGURATION & GLOBAL VARIABLES
# ------------------------------------------------------------------------------

LOG_FILE="/var/log/freebsd_setup.log"
USERNAME="sawyer"

# Essential Package List (space-delimited)
PACKAGES="bash zsh fish vim nano emacs mc neovim screen tmux \
gcc gmake cmake meson intltool gettext pigz libtool pkgconf bzip2 xz git hugo \
acpid chrony fail2ban sudo bash-completion logrotate net-tools \
curl wget tcpdump rsync nmap lynx bind-tools mtr netcat socat \
htop neofetch tig jq vnstat tree fzf smartmontools lsof sysstat \
gdisk fusefs-ntfs ncdu unzip zip parted lvm2 \
perl patch bc gawk expect \
fd-find bat ripgrep hyperfine cheat \
ffmpeg restic mpv \
ranger nnn \
muttr newsboat irssi weechat httpie youtube_dl \
taskwarrior calcurse \
asciinema \
cowsay figlet"

# Nord Color Theme (for logging)
RED='\033[38;2;191;97;106m'
YELLOW='\033[38;2;235;203;139m'
GREEN='\033[38;2;163;190;140m'
BLUE='\033[38;2;94;129;172m'
NC='\033[0m'

# ------------------------------------------------------------------------------
# 2. UTILITY & LOGGING FUNCTIONS
# ------------------------------------------------------------------------------

log() {
    local level message timestamp color
    level=$(echo "$1" | tr '[:lower:]' '[:upper:]')
    shift
    message="$*"
    timestamp=$(date +"%Y-%m-%d %H:%M:%S")
    case "$level" in
        INFO)  color="${GREEN}" ;;
        WARN*) color="${YELLOW}" ;;
        ERROR) color="${RED}" ;;
        *)     color="${NC}" ;;
    esac
    # Log to both terminal and file
    printf "%b[%s] [%s] %s%b\n" "$color" "$timestamp" "$level" "$message" "$NC" | tee -a "$LOG_FILE"
}

warn() {
    log WARN "$@"
}

die() {
    log ERROR "$@"
    exit 1
}

# ------------------------------------------------------------------------------
# 3. SYSTEM PREPARATION FUNCTIONS
# ------------------------------------------------------------------------------

# Ensure the script is run as root
check_root() {
    if [ "$(id -u)" -ne 0 ]; then
        die "Script must be run as root. Exiting."
    fi
}

# Check for network connectivity by pinging a reliable host
check_network() {
    log INFO "Checking network connectivity..."
    if ! ping -c 1 -W 5 google.com >/dev/null 2>&1; then
        die "No network connectivity. Please verify your network settings."
    fi
    log INFO "Network connectivity verified."
}

# Update package repositories and upgrade system packages
update_system() {
    log INFO "Updating package repositories..."
    if ! pkg update -q; then
        die "Failed to update package repositories."
    fi

    log INFO "Upgrading system packages..."
    if ! pkg upgrade -y; then
        die "Failed to upgrade packages."
    fi
}

# Create the specified user if it does not already exist
ensure_user() {
    if pw usershow "$USERNAME" >/dev/null 2>&1; then
        log INFO "User '$USERNAME' already exists."
    else
        log INFO "Creating user '$USERNAME'..."
        if ! pw useradd "$USERNAME" -m -s /bin/sh -w no; then
            die "Failed to create user '$USERNAME'."
        fi
    fi
}

# Install essential system packages
install_packages() {
    log INFO "Installing essential packages..."
    if ! pkg install -y ${PACKAGES}; then
        die "Failed to install one or more packages."
    fi
}

i3_config() {
    log INFO "Installing i3 window manager and its addons..."

    # Install i3 and common add-ons
    if ! pkg install -y i3 i3status i3lock dmenu i3blocks; then
        die "Failed to install i3 and its addons."
    fi

    # Ensure the ninja build tool is available (required for building ly)
    if ! command -v ninja >/dev/null 2>&1; then
        log INFO "Installing ninja build system..."
        if ! pkg install -y ninja; then
            die "Failed to install ninja."
        fi
    fi

    log INFO "Cloning and installing ly login manager from GitHub..."

    # Define the source directory for ly
    LY_SRC="/usr/local/src/ly"
    LY_REPO="https://github.com/nullgemm/ly.git"

    # Clone or update the ly repository
    if [ -d "${LY_SRC}/ly" ]; then
        log INFO "Updating existing ly repository in ${LY_SRC}/ly..."
        cd "${LY_SRC}/ly" || die "Cannot change directory to ${LY_SRC}/ly"
        if ! git pull; then
            warn "Failed to update ly repository; continuing with existing code."
        fi
    else
        log INFO "Cloning ly repository into ${LY_SRC}..."
        mkdir -p "${LY_SRC}" || die "Failed to create directory ${LY_SRC}"
        cd "${LY_SRC}" || die "Cannot change directory to ${LY_SRC}"
        if ! git clone "$LY_REPO"; then
            die "Failed to clone ly repository from ${LY_REPO}"
        fi
        cd ly || die "Cannot change directory to ly"
    fi

    # Remove any previous build directory to ensure a clean build
    if [ -d "build" ]; then
        log INFO "Removing existing build directory..."
        rm -rf build || warn "Could not remove existing build directory."
    fi

    # Build and install ly using meson and ninja
    log INFO "Setting up build environment for ly..."
    if ! meson setup build; then
        die "meson setup for ly failed."
    fi

    log INFO "Building ly..."
    if ! ninja -C build; then
        die "ninja build for ly failed."
    fi

    log INFO "Installing ly..."
    if ! ninja -C build install; then
        die "Installation of ly failed."
    fi

    # Enable ly to start automatically at boot
    log INFO "Enabling ly display manager to start at boot..."
    if ! sysrc ly_enable=YES; then
        warn "Failed to enable ly in rc.conf."
    else
        log INFO "ly display manager enabled."
    fi

    # Optionally, start the ly service immediately (a reboot might be required to see full effect)
    if ! service ly start; then
        warn "Failed to start ly display manager immediately."
    else
        log INFO "ly display manager started."
    fi

    log INFO "i3 and ly configuration complete. You can now choose your desktop session at login."
}

# ------------------------------------------------------------------------------
# 4. CORE CONFIGURATION FUNCTIONS
# ------------------------------------------------------------------------------

# Harden and configure the SSH server
configure_ssh() {
    log INFO "Configuring SSH server..."
    sysrc sshd_enable=YES

    SSH_CONFIG="/etc/ssh/sshd_config"
    if [ -f "$SSH_CONFIG" ]; then
        cp "$SSH_CONFIG" "${SSH_CONFIG}.bak"
        log INFO "Backup of SSH config saved as ${SSH_CONFIG}.bak"
        sed -i '' -e 's/^#\?PermitRootLogin.*/PermitRootLogin no/' \
                  -e 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' \
                  -e 's/^#\?PermitEmptyPasswords.*/PermitEmptyPasswords no/' "$SSH_CONFIG"
        if ! service sshd restart; then
            die "Failed to restart SSH service."
        fi
        log INFO "SSH configuration updated and service restarted."
    else
        warn "SSH configuration file not found at $SSH_CONFIG."
    fi
}

# Configure PF (Packet Filter) firewall
configure_pf() {
    log INFO "Configuring PF firewall..."
    sysrc pf_enable=YES
    sysrc pflog_enable=YES

    PF_CONF="/etc/pf.conf"
    cat > "$PF_CONF" <<'EOF'
# PF Firewall Configuration

# Define external interface (adjust if necessary)
ext_if = "vtnet0"

# Trusted network (modify as needed)
trusted = "{ 192.168.1.0/24 }"

# Skip loopback interface
set skip on lo

# Default deny policy
block all
pass out quick keep state

# Allow SSH connections
pass in on $ext_if proto tcp to port 22

# Allow HTTP/HTTPS traffic
pass in on $ext_if proto tcp to port { 80, 443 }

# Allow Plex Media Server access
pass in on $ext_if proto tcp to port 32400
EOF

    log INFO "PF configuration written to $PF_CONF."
    if ! service pf restart; then
        die "Failed to restart PF firewall."
    fi
    log INFO "PF firewall configured and restarted."
}

# Enable and start the fail2ban service
configure_fail2ban() {
    log INFO "Enabling fail2ban service..."
    sysrc fail2ban_enable=YES
    if ! service fail2ban start; then
        warn "Failed to start fail2ban service."
    else
        log INFO "fail2ban service started successfully."
    fi
}

# ------------------------------------------------------------------------------
# 5. STORAGE & SERVICES CONFIGURATION
# ------------------------------------------------------------------------------

# Install and configure Plex Media Server
install_plex() {
    log INFO "Installing Plex Media Server..."
    if ! pkg install -y plexmediaserver; then
        die "Plex Media Server installation failed."
    fi

    sysrc plexmediaserver_uid="$USERNAME"
    sysrc plexmediaserver_enable=YES
    if ! service plexmediaserver start; then
        warn "Plex Media Server failed to start."
    else
        log INFO "Plex Media Server installed and started."
    fi
}

# Configure ZFS: load module, enable at boot, and import pool if necessary
configure_zfs() {
    log INFO "Configuring ZFS..."
    if ! kldload zfs; then
        die "Failed to load ZFS kernel module."
    fi
    sysrc zfs_enable=YES

    ZPOOL_NAME="WD_BLACK"
    if ! zpool list "$ZPOOL_NAME" >/dev/null 2>&1; then
        log INFO "Importing ZFS pool '$ZPOOL_NAME'..."
        if ! zpool import "$ZPOOL_NAME"; then
            die "Failed to import ZFS pool '$ZPOOL_NAME'."
        fi
    fi

    if ! zfs set mountpoint=/media/"$ZPOOL_NAME" "$ZPOOL_NAME"; then
        warn "Failed to set mountpoint for ZFS pool '$ZPOOL_NAME'."
    else
        log INFO "ZFS pool '$ZPOOL_NAME' mountpoint set to /media/$ZPOOL_NAME."
    fi
}

# Clone GitHub repositories into the user's home directory
setup_repos() {
    log INFO "Setting up GitHub repositories for user '$USERNAME'..."
    GH_DIR="/home/$USERNAME/github"
    if ! mkdir -p "$GH_DIR"; then
        die "Failed to create GitHub directory at $GH_DIR."
    fi

    for repo in bash windows web python go misc; do
        REPO_DIR="$GH_DIR/$repo"
        [ -d "$REPO_DIR" ] && {
            log INFO "Removing existing directory for repository '$repo'."
            rm -rf "$REPO_DIR"
        }
        if ! git clone "https://github.com/dunamismax/$repo.git" "$REPO_DIR"; then
            warn "Failed to clone repository '$repo'."
        else
            chown -R "$USERNAME:$USERNAME" "$REPO_DIR"
            log INFO "Repository '$repo' cloned successfully."
        fi
    done
}

# ------------------------------------------------------------------------------
# 6. DOCKER CONFIGURATION
# ------------------------------------------------------------------------------

# Install Docker and Docker Compose, enable the service, and add the user to the docker group
install_docker() {
    log INFO "Installing Docker and Docker Compose..."
    if ! pkg install -y docker docker-compose; then
        die "Docker installation failed."
    fi

    sysrc docker_enable=YES
    if ! service docker start; then
        die "Failed to start Docker service."
    fi

    if ! pw groupmod docker -m "$USERNAME"; then
        warn "Failed to add user '$USERNAME' to docker group."
    else
        log INFO "User '$USERNAME' added to docker group."
    fi
}

# ------------------------------------------------------------------------------
# 7. FINALIZATION
# ------------------------------------------------------------------------------

# Configure periodic system maintenance tasks
configure_periodic() {
    log INFO "Configuring periodic system maintenance tasks..."
    PERIODIC_CONF="/etc/periodic.conf"
    {
        echo 'daily_system_updates_enable="YES"'
        echo 'daily_status_security_enable="YES"'
    } >> "$PERIODIC_CONF"
    log INFO "Periodic tasks added to $PERIODIC_CONF."
}

# Log final system status
final_checks() {
    log INFO "Performing final system checks..."
    log INFO "Kernel version: $(uname -r)"
    log INFO "Disk usage: $(df -h /)"
    log INFO "Physical memory: $(sysctl -n hw.physmem) bytes"
}

# Prompt for system reboot after a brief delay
prompt_reboot() {
    log INFO "Setup complete. The system will reboot in 10 seconds. Press Ctrl+C to cancel."
    sleep 10
    shutdown -r now
}

# ------------------------------------------------------------------------------
# MAIN EXECUTION
# ------------------------------------------------------------------------------

main() {
    check_root
    check_network
    update_system
    ensure_user
    install_packages
    configure_ssh
    configure_pf
    configure_fail2ban
    install_plex
    configure_zfs
    setup_repos
    install_docker
    configure_periodic
    i3_config
    final_checks
    prompt_reboot
}

main "$@"