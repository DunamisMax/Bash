#!/usr/bin/env bash
# ------------------------------------------------------------------------------
# Ubuntu Automated Setup Script
# ------------------------------------------------------------------------------
# Automates fresh system configuration:
#  • Updates repositories, installs/upgrades essential software.
#  • Backs up and customizes key configuration files for security and performance.
#  • Sets up user "sawyer" with sudo privileges and a configured Bash environment.
#  • Enables/configures services: UFW, SSH, Chrony, etc.
#  • Installs optional tools: Caddy, Plex, Python, Go, Rust, Zig, etc.
#
# Usage:
#  • Run as root or via sudo.
#  • Adjust variables (USERNAME, PACKAGES, etc.) as needed.
#  • Logs actions/errors to /var/log/ubuntu_setup.log with timestamps.
#
# Error Handling:
#  • Uses 'set -euo pipefail' and an ERR trap for robust failure management.
#
# Compatibility:
#  • Tested on Ubuntu 24.10. Verify on other versions.
#
# Author: dunamismax | License: MIT
# ------------------------------------------------------------------------------

set -Eeuo pipefail

# ------------------------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------------------------
LOG_FILE="/var/log/ubuntu_setup.log"
VERBOSE=2
USERNAME="sawyer"

PACKAGES=(
  bash zsh fish vim nano mc screen tmux nodejs npm
  build-essential cmake hugo pigz exim4 openssh-server libtool pkg-config libssl-dev
  bzip2 libbz2-dev libffi-dev zlib1g-dev libreadline-dev libsqlite3-dev tk-dev
  xz-utils libncurses5-dev python3 python3-dev python3-pip python3-venv libfreetype6-dev
  git ufw perl curl wget tcpdump rsync htop passwd bash-completion neofetch tig jq
  nmap tree fzf lynx which patch smartmontools ntfs-3g ubuntu-restricted-extras
  qemu-kvm libvirt-daemon-system libvirt-clients virtinst bridge-utils
  chrony fail2ban ffmpeg restic
)

# ------------------------------------------------------------------------------
# MAIN SCRIPT START
# You can add functions below (e.g., apt updates, config overwrites) and then
# call them in your "main" block at the end.
# ------------------------------------------------------------------------------

################################################################################
# Function: logging function
################################################################################
log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp
    timestamp=$(date +"%Y-%m-%d %H:%M:%S")

    # Define color codes
    local RED='\033[0;31m'
    local YELLOW='\033[0;33m'
    local GREEN='\033[0;32m'
    local BLUE='\033[0;34m'
    local NC='\033[0m'  # No Color

    # Validate log level and set color
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

    # Ensure the log file exists and is writable
    if [[ -z "${LOG_FILE:-}" ]]; then
        LOG_FILE="/var/log/example_script.log"
    fi
    if [[ ! -e "$LOG_FILE" ]]; then
        mkdir -p "$(dirname "$LOG_FILE")"
        touch "$LOG_FILE"
        chmod 644 "$LOG_FILE"
    fi

    # Format the log entry
    local log_entry="[$timestamp] [$level] $message"

    # Append to log file
    echo "$log_entry" >> "$LOG_FILE"

    # Output to console based on verbosity
    if [[ "$VERBOSE" -ge 2 ]]; then
        printf "${color}%s${NC}\n" "$log_entry" >&2
    elif [[ "$VERBOSE" -ge 1 && "$level" == "ERROR" ]]; then
        printf "${color}%s${NC}\n" "$log_entry" >&2
    fi
}

################################################################################
# Function: handle_error
################################################################################
handle_error() {
  log ERROR "An error occurred. Check the log for details."
}

# Trap any error and output a helpful message
trap 'log ERROR "Script failed at line $LINENO. See above for details."' ERR

# ------------------------------------------------------------------------------
# Backup Function
# ------------------------------------------------------------------------------
backup_system() {
    apt install -y rsync
    # Variables
    local SOURCE="/"                       # Source directory for backup
    local DESTINATION="/home/sawyer/BACKUPS" # Destination for backups
    local TIMESTAMP
    TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S") # Timestamp for folder naming
    local BACKUP_FOLDER="$DESTINATION/backup-$TIMESTAMP" # Custom dated folder
    local RETENTION_DAYS=7                 # Retain backups for 7 days
    # Exclusions for the backup
    local EXCLUDES=(
        "/proc/*"
        "/sys/*"
        "/dev/*"
        "/run/*"
        "/tmp/*"
        "/mnt/*"
        "/media/*"
        "/swapfile"
        "/lost+found"
        "/var/tmp/*"
        "/var/cache/*"
        "/var/log/*"
        "/var/lib/lxcfs/*"
        "/var/lib/docker/*"
        "/root/.cache/*"
        "/home/*/.cache/*"
        "/var/lib/plexmediaserver/*"
        "$DESTINATION"
    )
    # Create exclusion string for rsync
    local EXCLUDES_ARGS=()
    for EXCLUDE in "${EXCLUDES[@]}"; do
        EXCLUDES_ARGS+=(--exclude="$EXCLUDE")
    done
    # Ensure the destination folder exists
    mkdir -p "$BACKUP_FOLDER"
    # Perform backup using rsync
    log INFO "Starting system backup to $BACKUP_FOLDER"
    if rsync -aAXv "${EXCLUDES_ARGS[@]}" "$SOURCE" "$BACKUP_FOLDER"; then
        log INFO "Backup completed successfully: $BACKUP_FOLDER"
    else
        log ERROR "Error: Backup process failed."
        exit 1
    fi
    # Remove old backups
    log INFO "Cleaning up old backups older than $RETENTION_DAYS days."
    if find "$DESTINATION" -type d -name "backup-*" -mtime +"$RETENTION_DAYS" -exec rm -rf {} \;; then
        log INFO "Old backups removed."
    else
        log WARN "Warning: Failed to remove some old backups."
    fi
}

# ------------------------------------------------------------------------------
# FIX DIRECTORY PERMISSIONS FUNCTION
# ------------------------------------------------------------------------------

# Configuration
GITHUB_DIR="/home/sawyer/github"
HUGO_PUBLIC_DIR="/home/sawyer/github/hugo/dunamismax.com/public"
HUGO_DIR="/home/sawyer/github/hugo"
SAWYER_HOME="/home/sawyer"
BASE_DIR="/home/sawyer/github"
DIR_PERMISSIONS="755"  # Directories: rwx for owner, rx for group/others
FILE_PERMISSIONS="644" # Files: rw for owner, r for group/others

# ------------------------------------------------------------------------------
# FUNCTION: fix_git_permissions
# ------------------------------------------------------------------------------
fix_git_permissions() {
    local git_dir="$1"
    echo "Setting permissions for $git_dir"
    chmod "$DIR_PERMISSIONS" "$git_dir"
    find "$git_dir" -type d -exec chmod "$DIR_PERMISSIONS" {} \;
    find "$git_dir" -type f -exec chmod "$FILE_PERMISSIONS" {} \;
    echo "Permissions fixed for $git_dir"
}

# ------------------------------------------------------------------------------
# MAIN FUNCTION: set_directory_permissions
# ------------------------------------------------------------------------------
set_directory_permissions() {
  # 1. Make all .sh files executable under GITHUB_DIR
  log INFO "Making all .sh files executable under $GITHUB_DIR"
  find "$GITHUB_DIR" -type f -name "*.sh" -exec chmod +x {} \;

  # 2. Set ownership for directories
  log INFO "Setting ownership for /home/sawyer/github and /home/sawyer"
  chown -R sawyer:sawyer /home/sawyer/github
  chown -R sawyer:sawyer /home/sawyer/

  # 3. Set ownership and permissions for Hugo public directory
  log INFO "Setting ownership and permissions for Hugo public directory"
  chown -R www-data:www-data "$HUGO_PUBLIC_DIR"
  chmod -R 755 "$HUGO_PUBLIC_DIR"

  # 4. Set ownership and permissions for Hugo directory and related paths
  log INFO "Setting ownership and permissions for Hugo directory"
  chown -R caddy:caddy "$HUGO_DIR"
  chmod o+rx "$SAWYER_HOME"
  chmod o+rx "$GITHUB_DIR"
  chmod o+rx "$HUGO_DIR"
  chmod o+rx "/home/sawyer/github/hugo/dunamismax.com"

  # 5. Ensure BASE_DIR exists
  if [[ ! -d "$BASE_DIR" ]]; then
      echo "Error: Base directory $BASE_DIR does not exist."
      exit 1
  fi

  log INFO "Starting permission fixes in $BASE_DIR..."

  # 6. Find and fix .git directory permissions
  # Loop over each .git directory found within BASE_DIR
  while IFS= read -r -d '' git_dir; do
      fix_git_permissions "$git_dir"
  done < <(find "$BASE_DIR" -type d -name ".git" -print0)

  log INFO "Permission setting completed."
}

# To execute the function, simply call:
# set_directory_permissions

################################################################################
# Function: Configure SSH and security settings
# Purpose: Install and configure OpenSSH server with best practices for security
################################################################################
configure_ssh_settings() {
  log INFO "Installing OpenSSH Server..."
  
  # Install OpenSSH server if not already installed
  if ! dpkg -l | grep -qw openssh-server; then
    apt update && apt install -y openssh-server
    log INFO "OpenSSH Server installed."
  else
    log INFO "OpenSSH Server is already installed."
  fi

  # Enable and start SSH service
  systemctl enable --now ssh
  log INFO "ssh service enabled and started."

  log INFO "Configuring SSH settings in /etc/ssh/sshd_config..."

  # Backup sshd_config before making changes
  local sshd_config="/etc/ssh/sshd_config"
  local backup_file="${sshd_config}.bak.$(date +%Y%m%d%H%M%S)"
  cp "$sshd_config" "$backup_file" && log INFO "Backup created at $backup_file."

  # Define desired SSH settings for the server
  declare -A sshd_settings=(
    ["Port"]="22"
    ["MaxAuthTries"]="8"
    ["MaxSessions"]="6"
    ["PermitRootLogin"]="no"
    ["Protocol"]="2"
  )

  # Apply SSH server settings
  for setting in "${!sshd_settings[@]}"; do
    if grep -q "^${setting} " "$sshd_config"; then
      sed -i "s/^${setting} .*/${setting} ${sshd_settings[$setting]}/" "$sshd_config"
    else
      echo "${setting} ${sshd_settings[$setting]}" >> "$sshd_config"
    fi
  done

  log INFO "SSH server configuration updated. Restarting SSH service..."

  # Restart SSH service and handle errors
  if systemctl restart sshd; then
    log INFO "sshd service restarted successfully."
  else
    log ERROR "Failed to restart sshd service. Please check the configuration."
    return 1
  fi
}

################################################################################
# Function: bootstrap_and_install_pkgs
################################################################################
bootstrap_and_install_pkgs() {
  log INFO "Updating apt package list and upgrading existing packages..."
  apt update -y
  apt upgrade -y

  local packages_to_install=()
  for pkg in "${PACKAGES[@]}"; do
    # If not installed, queue it up for installation
    if ! dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q "install ok installed"; then
      packages_to_install+=("$pkg")
    else
      log INFO "Package '$pkg' is already installed."
    fi
  done

  if [ ${#packages_to_install[@]} -gt 0 ]; then
    log INFO "Installing packages: ${packages_to_install[*]}"
    apt install -y "${packages_to_install[@]}"
  else
    log INFO "All listed packages are already installed. No action needed."
  fi

  apt autoremove -y
  apt clean -y

  log INFO "Package installation process completed."
}

################################################################################
# Function: set_default_shell_and_env
################################################################################
set_default_shell_and_env() {
  log INFO "Recreating .profile, .bash_profile, and .bashrc for $USERNAME..."

  # Dynamically determine the user's home directory
  local user_home
  user_home=$(eval echo "~$USERNAME")

  # File paths
  local bashrc_file="$user_home/.bashrc"
  local bash_profile_file="$user_home/.bash_profile"
  local profile_file="$user_home/.profile"

  # Overwrite the .bash_profile file with the specified contents
  log INFO "Creating $bash_profile_file with default content..."
  cat << 'EOF' > "$bash_profile_file"
# ~/.bash_profile
# Always source ~/.bashrc to ensure consistent shell environment setup
if [ -f ~/.bashrc ]; then
    source ~/.bashrc
fi
EOF

  # Set ownership and permissions for the .bash_profile file
  chown "$USERNAME":"$USERNAME" "$bash_profile_file"
  chmod 644 "$bash_profile_file"
  log INFO ".bash_profile created successfully."

  # Overwrite the .profile file with the specified contents (like .bash_profile)
  log INFO "Creating $profile_file with default content..."
  cat << 'EOF' > "$profile_file"
# ~/.profile
# Always source ~/.bashrc to ensure consistent shell environment setup
if [ -f ~/.bashrc ]; then
    . ~/.bashrc
fi
EOF

  # Set ownership and permissions for the .profile file
  chown "$USERNAME":"$USERNAME" "$profile_file"
  chmod 644 "$profile_file"
  log INFO ".profile created successfully."

  # Overwrite the .bashrc file
  log INFO "Creating $bashrc_file with default content..."
  cat << 'EOF' > "$bashrc_file"
# ~/.bashrc: executed by bash(1) for non-login shells.
# ------------------------------------------------------------------------------
#    ______                  ______
#    ___  /_ ______ ____________  /_ _______________
#    __  __ \_  __ `/__  ___/__  __ \__  ___/_  ___/
#___ _  /_/ // /_/ / _(__  ) _  / / /_  /    / /__
#_(_)/_.___/ \__,_/  /____/  /_/ /_/ /_/     \___/
#
# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
# 1. Early return if not running interactively
# ------------------------------------------------------------------------------
case $- in
    *i*) ;;
      *) return;;
esac

# ------------------------------------------------------------------------------
# 2. Environment variables
# ------------------------------------------------------------------------------
# Add your local bin directory to PATH.
export PATH="$PATH:$HOME/.local/bin"
export GDK_BACKEND=wayland
export QT_QPA_PLATFORM=wayland
export CLUTTER_BACKEND=wayland
export XDG_SESSION_TYPE=wayland

# ------------------------------------------------------------------------------
# 3. pyenv initialization
# ------------------------------------------------------------------------------
# Adjust these lines according to your Python environment needs.
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"

if command -v pyenv 1>/dev/null 2>&1; then
    # Initialize pyenv so that it can manage your Python versions and virtualenvs.
    eval "$(pyenv init --path)"
    eval "$(pyenv init -)"
fi

# ------------------------------------------------------------------------------
# 4. History preferences
# ------------------------------------------------------------------------------
# Do not store duplicate lines or lines that start with a space in the history.
HISTCONTROL=ignoreboth

# Allow appending to the history file (instead of overwriting it).
shopt -s histappend

# Set history limits (number of lines in memory / on disk).
HISTSIZE=100000
HISTFILESIZE=200000

# Add timestamps to each command in history (for auditing).
HISTTIMEFORMAT="%F %T "

# Re-check window size after each command, updating LINES and COLUMNS if needed.
shopt -s checkwinsize

# ------------------------------------------------------------------------------
# 5. Less (pager) setup
# ------------------------------------------------------------------------------
# Make 'less' more friendly for non-text input files, see lesspipe(1).
[ -x /usr/bin/lesspipe ] && eval "$(SHELL=/bin/sh lesspipe)"

# ------------------------------------------------------------------------------
# 6. Bash prompt (PS1)
# ------------------------------------------------------------------------------
# If terminal supports color, enable a colored prompt.
case "$TERM" in
    xterm-color|*-256color) color_prompt=yes;;
esac

# Uncomment the line below if you always want a color prompt (if supported).
force_color_prompt=yes

if [ -n "$force_color_prompt" ]; then
    if [ -x /usr/bin/tput ] && tput setaf 1 >&/dev/null; then
        # We have color support; assume it's compliant with Ecma-48 (ISO/IEC-6429).
        color_prompt=yes
    else
        color_prompt=
    fi
fi

# Choose a colored or plain prompt.
if [ "$color_prompt" = yes ]; then
    PS1='${ubuntu_chroot:+($ubuntu_chroot)}\[\033[01;32m\]\u@\h\[\033[00m\]:\[\033[01;34m\]\w\[\033[00m\]\$ '
else
    PS1='${ubuntu_chroot:+($ubuntu_chroot)}\u@\h:\w\$ '
fi
unset color_prompt force_color_prompt

# If this is an xterm or rxvt terminal, set the window title to user@host:dir.
case "$TERM" in
    xterm*|rxvt*)
        PS1="\[\e]0;${ubuntu_chroot:+($ubuntu_chroot)}\u@\h: \w\a\]$PS1"
        ;;
    *)
        ;;
esac

# ------------------------------------------------------------------------------
# 7. Color support for common commands
# ------------------------------------------------------------------------------
if [ -x /usr/bin/dircolors ]; then
    test -r ~/.dircolors && eval "$(dircolors -b ~/.dircolors)" || eval "$(dircolors -b)"
    alias ls='ls --color=auto'
    # alias dir='dir --color=auto'
    # alias vdir='vdir --color=auto'

    alias grep='grep --color=auto'
    alias fgrep='fgrep --color=auto'
    alias egrep='egrep --color=auto'
fi

# ------------------------------------------------------------------------------
# 8. Handy aliases
# ------------------------------------------------------------------------------
# Basic ls aliases
alias ll='ls -alF'
alias la='ls -A'
alias l='ls -CF'

# Launch ranger file manager
alias r='ranger'

# Alert alias for long running commands (use: sleep 10; alert)
alias alert='notify-send --urgency=low -i "$([ $? = 0 ] && echo terminal || echo error)" \
"$(history|tail -n1|sed -e '\''s/^\s*[0-9]\+\s*//;s/[;&|]\s*alert$//'\'')"'

# ------------------------------------------------------------------------------
# 9. Python virtual environment functions and aliases
# ------------------------------------------------------------------------------
# Alias to quickly set up a new Python virtual environment
alias venv='setup_venv'
# Alias to quickly re-enable an existing Python virtual environment
alias v='enable_venv'

# Function to set up a new Python virtual environment in the current directory
setup_venv() {
    # If there's already a venv active, deactivate it first
    if type deactivate &>/dev/null; then
        echo "Deactivating current virtual environment..."
        deactivate
    fi

    echo "Creating a new virtual environment in $(pwd)/.venv..."
    python -m venv .venv

    echo "Activating the virtual environment..."
    source .venv/bin/activate

    if [ -f requirements.txt ]; then
        echo "Installing dependencies from requirements.txt..."
        pip install -r requirements.txt
    else
        echo "No requirements.txt found. Skipping pip install."
    fi

    echo "Virtual environment setup complete."
}

# Function to re-enable an existing Python virtual environment in the current directory
enable_venv() {
    # If there's already a venv active, deactivate it first
    if type deactivate &>/dev/null; then
        echo "Deactivating current virtual environment..."
        deactivate
    fi

    echo "Activating the virtual environment..."
    source .venv/bin/activate

    if [ -f requirements.txt ]; then
        echo "Installing dependencies from requirements.txt..."
        pip install -r requirements.txt
    else
        echo "No requirements.txt found. Skipping pip install."
    fi

    echo "Virtual environment setup complete."
}

# ------------------------------------------------------------------------------
# 10. Load user-defined aliases from ~/.bash_aliases (if it exists)
# ------------------------------------------------------------------------------
if [ -f ~/.bash_aliases ]; then
    . ~/.bash_aliases
fi

# ------------------------------------------------------------------------------
# 11. Bash completion
# ------------------------------------------------------------------------------
# Enable programmable completion features if not in POSIX mode.
# (Examples: git completion, docker completion, etc.)
if ! shopt -oq posix; then
    if [ -f /usr/share/bash-completion/bash_completion ]; then
        . /usr/share/bash-completion/bash_completion
    elif [ -f /etc/bash_completion ]; then
        . /etc/bash_completion
    fi
fi

# ------------------------------------------------------------------------------
# End of ~/.bashrc
# ------------------------------------------------------------------------------
EOF

  chown "$USERNAME":"$USERNAME" "$bashrc_file" "$bash_profile_file" "$profile_file"
  chmod 644 "$bashrc_file" "$bash_profile_file" "$profile_file"

  log INFO "Bash configuration files (.profile, .bash_profile, and .bashrc) have been recreated for $USERNAME."
}

###############################################################################
# Enable and configure ufw.
###############################################################################
configure_ufw() {
  log INFO "Enabling ufw systemd service..."
  # Ensure ufw starts on boot, then start it now
  systemctl enable ufw
  systemctl start ufw

  log INFO "Activating ufw (will allow pre-configured rules)..."
  # --force ensures it doesn’t prompt for confirmation
  ufw --force enable

  log INFO "Configuring ufw rules..."
  ufw allow ssh
  ufw allow http
  ufw allow 8080/tcp
  ufw allow 80/tcp
  ufw allow 80/udp
  ufw allow 443/tcp
  ufw allow 443/udp
  ufw allow 32400/tcp
  ufw allow 1900/udp
  ufw allow 5353/udp
  ufw allow 8324/tcp
  ufw allow 32410/udp
  ufw allow 32411/udp
  ufw allow 32412/udp
  ufw allow 32413/udp
  ufw allow 32414/udp
  ufw allow 32415/udp
  ufw allow 32469/tcp

  log INFO "UFW configuration complete."
}

###############################################################################
# Function: force_release_ports
###############################################################################
force_release_ports() {
  # Step 1: Remove Apache and Caddy, then autoremove
  log INFO "Removing apache2 and caddy..."
  apt purge -y apache2
  apt purge -y caddy
  apt autoremove -y

  # Step 2: Install net-tools if not present
  log INFO "Installing net-tools..."
  apt install -y net-tools

  # Step 3: Define ports to kill (TCP and UDP separately)
  local tcp_ports=("8080" "80" "443" "32400" "8324" "32469")
  local udp_ports=("80" "443" "1900" "5353" "32410" "32411" "32412" "32413" "32414" "32415")

  log INFO "Killing any processes listening on the specified ports..."

  # Kill TCP processes
  for p in "${tcp_ports[@]}"; do
    # lsof -t: print only the process IDs
    # -i TCP:$p: match TCP port
    # -sTCP:LISTEN: only processes in LISTEN state
    pids="$(lsof -t -i TCP:"$p" -sTCP:LISTEN 2>/dev/null || true)"
    if [ -n "$pids" ]; then
      echo "Killing processes on TCP port $p: $pids"
      kill -9 $pids
    fi
  done

  # Kill UDP processes
  for p in "${udp_ports[@]}"; do
    # -i UDP:$p: match UDP port
    pids="$(lsof -t -i UDP:"$p" 2>/dev/null || true)"
    if [ -n "$pids" ]; then
      log INFO "Killing processes on UDP port $p: $pids"
      kill -9 $pids
    fi
  done

  log INFO "Ports have been forcibly released."
}

################################################################################
# Function: configure_timezone
################################################################################
configure_timezone() {
  local tz="${1:-UTC}"  # Default to UTC if not specified
  log INFO "Configuring timezone to '${tz}'..."

  # Ensure tzdata is present (usually installed by default, but just in case)
  apt install -y tzdata

  # Timedatectl sets both system clock and hardware clock
  timedatectl set-timezone "$tz"

  log INFO "Timezone set to $tz."
}

################################################################################
# Function: fail2ban
################################################################################
fail2ban() {
  log INFO "Installing fail2ban..."

  # 1) Install fail2ban (from ubuntu repositories)
  if ! dpkg-query -W -f='${Status}' fail2ban 2>/dev/null | grep -q "install ok installed"; then
    log INFO "Installing fail2ban..."
    apt install -y fail2ban
    systemctl enable fail2ban
    systemctl start fail2ban
  else
    log INFO "fail2ban is already installed."
  fi

  log INFO "Security hardening steps completed."
}

################################################################################
# Function: download_repositories
################################################################################
download_repositories() {
  log INFO "Downloading github repositories"

  log INFO "Creating github directory"
  mkdir -p /home/sawyer/github

  log INFO "Changing to github directory"
  cd /home/sawyer/github

  # Clone repositories if they do not already exist
  git clone "https://github.com/dunamismax/bash.git"
  git clone "https://github.com/dunamismax/c.git"
  git clone "https://github.com/dunamismax/religion.git"
  git clone "https://github.com/dunamismax/windows.git"
  git clone "https://github.com/dunamismax/hugo.git"
  git clone "https://github.com/dunamismax/python.git"
  log INFO "Download completed"

  # Set permissions and ownership for the Hugo directory
  log INFO "Setting ownership and permissions for Hugo public directory"
  chown -R www-data:www-data "/home/sawyer/github/hugo/dunamismax.com/public"
  chmod -R 755 "/home/sawyer/github/hugo/dunamismax.com/public"

  log INFO "Setting ownership and permissions for Hugo directory"
  chown -R caddy:caddy "/home/sawyer/github/hugo"
  chmod o+rx "/home/sawyer/" "/home/sawyer/github/" "/home/sawyer/github/hugo/" "/home/sawyer/github/hugo/dunamismax.com/"

  log INFO "Update repositories and permissions completed."
  cd ~
}

################################################################################
# Function: create_caddyfile
################################################################################
create_caddyfile() {
  log INFO "Creating /etc/caddy/Caddyfile..."

  install_caddy

  local caddyfile_path="/etc/caddy/Caddyfile"
  local caddyfile_dir
  caddyfile_dir=$(dirname "$caddyfile_path")

  # Ensure caddy directory exists
  if [ ! -d "$caddyfile_dir" ]; then
    mkdir -p "$caddyfile_dir"
    log INFO "Created directory $caddyfile_dir"
  fi

  # Write out the Caddyfile
  cat << 'EOF' > "$caddyfile_path"
######################################################################
#                __________________         _____________ ______
# _____________ _______  /______  /_____  _____  __/___(_)___  /_____
# _  ___/_  __ `/_  __  / _  __  / __  / / /__  /_  __  / __  / _  _ \
# / /__  / /_/ / / /_/ /  / /_/ /  _  /_/ / _  __/  _  /  _  /  /  __/
# \___/  \__,_/  \__,_/   \__,_/   _\__, /  /_/     /_/   /_/   \___/
#                                  /____/
######################################################################

{
    # Use this email for Let's Encrypt notifications
    email dunamismax@tutamail.com

    # Global logging: captures all events (including errors during startup)
    log {
        output file /var/log/caddy/caddy.log
    }
}

# Redirect www to non-www
www.dunamismax.com {
    redir https://dunamismax.com{uri}
}

# Main website
dunamismax.com {
    # Serve the static files from your Hugo output folder
    root * /home/sawyer/github/hugo/dunamismax.com/public
    file_server

    # Deny hidden files (dotfiles like .git, .htaccess, etc.), except .well-known
    @hiddenFiles {
        path /.*
        not path /.well-known/*
    }
    respond @hiddenFiles 404

    # Per-site logging: captures site-specific access and error logs
    log {
        output file /var/log/caddy/dunamismax_access.log
    }
}

# Nextcloud
cloud.dunamismax.com {
    reverse_proxy 127.0.0.1:8080
}
EOF

  chown root:root "$caddyfile_path"
  chmod 644 "$caddyfile_path"

  log "Caddyfile created at $caddyfile_path"

  systemctl enable caddy
  systemctl start caddy

  # Optionally reload or restart Caddy to apply changes
  if command -v systemctl &>/dev/null; then
    log INFO "Reloading Caddy to apply new configuration..."
    systemctl reload caddy || {
      log ERROR "Reload failed, attempting restart..."
      systemctl restart caddy
    }
  fi
}

################################################################################
# Function: configure_ntp
################################################################################
configure_ntp() {
  log INFO "Configuring NTP (chrony)..."

  # 1) Install chrony if it is not already installed
  if ! dpkg-query -W -f='${Status}' chrony 2>/dev/null | grep -q "install ok installed"; then
    log INFO "Installing chrony..."
    apt install -y chrony
  else
    log INFO "chrony is already installed."
  fi

  # 2) Backup existing chrony config and overwrite
  local chrony_conf="/etc/chrony/chrony.conf"
  if [ -f "$chrony_conf" ]; then
    cp "$chrony_conf" "${chrony_conf}.bak.$(date +%Y%m%d%H%M%S)"
    log INFO "Backed up existing $chrony_conf to ${chrony_conf}.bak.$(date +%Y%m%d%H%M%S)"
  fi

  # 3) Write a basic chrony.conf (using global NTP servers for demonstration)
  cat << 'EOF' > "$chrony_conf"
# /etc/chrony/chrony.conf - basic configuration

# Pool-based time servers:
pool 2.ubuntu.pool.ntp.org iburst
pool time.google.com iburst
pool pool.ntp.org iburst

# Allow only localhost by default
allow 127.0.0.1
allow ::1

# Record the rate at which the system clock gains/losses time.
driftfile /var/lib/chrony/chrony.drift

# Save NTS keys and cookies.
ntsdumpdir /var/lib/chrony

# Enable kernel synchronization of the hardware clock
rtcsync

# Enable hardware timestamping on all interfaces that support it
hwtimestamp *

# Increase logging for debugging, comment out in production
log tracking measurements statistics
EOF

  log INFO "Wrote a new chrony.conf at $chrony_conf."

  # 4) Enable and start chrony
  systemctl enable chrony
  systemctl restart chrony

  log INFO "NTP (chrony) configuration complete."
}

################################################################################
# Function to install build dependencies for compiling Python via pyenv
################################################################################
install_python_build_deps() {

    log INFO "Installing system build dependencies..."

    # Install required packages
    if ! apt install -y \
        build-essential \
        git \
        curl \
        wget \
        ca-certificates \
        libssl-dev \
        libbz2-dev \
        libffi-dev \
        zlib1g-dev \
        libreadline-dev \
        libsqlite3-dev \
        libncurses5-dev \
        libncursesw5-dev \
        xz-utils \
        liblzma-dev \
        tk-dev \
        llvm \
        jq \
        gnupg \
        libxml2-dev \
        libxmlsec1-dev
        --no-install-recommends; then
        log ERROR "Failed to install build dependencies. Exiting."
        return 1
    fi

    # Clean up unnecessary packages and caches
    if ! apt autoremove -y; then
        log ERROR "Failed to autoremove unnecessary packages."
    fi

    if ! apt clean -y; then
        log ERROR "Failed to clean package cache."
    fi

    log INFO "System build dependencies installed."
}

# Function to install build dependencies for C, C++, Rust, and Go
install_dev_build_deps() {

    log INFO "Installing system build dependencies for C, C++, Rust, and Go..."

    # Install required packages
    if ! apt install -y \
        build-essential \
        gcc \
        g++ \
        clang \
        cmake \
        git \
        curl \
        wget \
        ca-certificates \
        make \
        llvm \
        gdb \
        libssl-dev \
        libbz2-dev \
        libffi-dev \
        zlib1g-dev \
        pkg-config \
        jq \
        gnupg \
        libxml2-dev \
        libxmlsec1-dev
        --no-install-recommends; then
        log ERROR "Failed to install build dependencies for C and C++. Exiting."
        return 1
    fi

    # Install Rust toolchain
    if ! curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y; then
        log ERROR "Failed to install Rust toolchain. Exiting."
        return 1
    fi

    # Add Rust binaries to PATH (for current session)
    export PATH="$HOME/.cargo/bin:$PATH"

    # Install Go (use apt for simplicity, but better alternatives exist)
    if ! apt install -y \
        golang-go; then
        log ERROR "Failed to install Go programming environment. Exiting."
        return 1
    fi

    # Clean up unnecessary packages and caches
    if ! apt autoremove -y; then
        log ERROR "Failed to autoremove unnecessary packages."
    fi

    if ! apt clean -y; then
        log ERROR "Failed to clean package cache."
    fi

    log INFO "System build dependencies for C, C++, Rust, and Go installed."
}

################################################################################
# 0. Basic System Update & Core Packages
################################################################################
install_apt_dependencies() {
    log INFO "Updating apt caches..."
    apt update -y

    # Optional: If you want to also upgrade existing packages:
    apt upgrade -y

    log INFO "Installing apt-based dependencies..."
    apt install -y --no-install-recommends \
        build-essential \
        make \
        git \
        curl \
        wget \
        vim \
        tmux \
        unzip \
        zip \
        ca-certificates \
        libssl-dev \
        libffi-dev \
        zlib1g-dev \
        libbz2-dev \
        libreadline-dev \
        libsqlite3-dev \
        libncursesw5-dev \
        libgdbm-dev \
        libnss3-dev \
        liblzma-dev \
        xz-utils \
        libxml2-dev \
        libxmlsec1-dev \
        tk-dev \
        llvm \
        software-properties-common \
        apt-transport-https \
        gnupg \
        lsb-release \
        jq

    # Optionally remove automatically installed packages no longer needed
    apt autoremove -y
    apt clean
}

################################################################################
# Function: install_caddy
################################################################################
install_caddy() {
  log INFO "Installing and enabling Caddy..."

  apt install -y ubuntu-keyring apt-transport-https curl

  # Add the official Caddy GPG key
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
    | gpg --batch --yes --dearmor \
         -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg

  # Add the Caddy stable repository
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
    | tee /etc/apt/sources.list.d/caddy-stable.list

  apt install -y caddy

  log INFO "Caddy installed."
}

################################################################################
# Function: install_and_enable_plex
################################################################################
install_and_enable_plex() {
  set -e  # Exit immediately if a command exits with a non-zero status

  log INFO "Checking if Plex Media Server is already installed..."
  if dpkg -s plexmediaserver >/dev/null 2>&1; then
    log INFO "Plex Media Server is already installed. Skipping installation."
    return
  fi

  log INFO "Updating apt package index..."
  apt update -y

  log INFO "Installing prerequisites (curl) if not already installed..."
  if ! dpkg -s curl >/dev/null 2>&1; then
    apt install -y curl
  fi

  # Change this to match the latest Plex version you want to install
  local VERSION="1.41.3.9314-a0bfb8370"
  local DEB_PACKAGE="plexmediaserver_${VERSION}_amd64.deb"
  local DEB_URL="https://downloads.plex.tv/plex-media-server-new/${VERSION}/debian/${DEB_PACKAGE}"

  log INFO "Downloading Plex Media Server package from Plex..."
  curl -LO "${DEB_URL}"

  log INFO "Installing Plex Media Server..."
  if ! dpkg -i "${DEB_PACKAGE}"; then
    log INFO "Resolving missing dependencies..."
    apt install -f -y
    dpkg -i "${DEB_PACKAGE}"
  fi

  log INFO "Configuring any partially installed packages..."
  dpkg --configure -a

  log INFO "Enabling and starting plexmediaserver service..."
  systemctl enable plexmediaserver
  systemctl start plexmediaserver

  log INFO "Plex Media Server installation complete!"
  log INFO "To configure Plex, open a browser on the same machine and go to:"
  log INFO "  http://127.0.0.1:32400/web"
}

# ------------------------------------------------------------------------------
# install_powershell_and_zig
#   Installs PowerShell and Zig on ubuntu/Linux ubuntu.
# ------------------------------------------------------------------------------
install_powershell_and_zig() {
  set -euo pipefail
  log INFO "Starting installation of PowerShell and Zig..."

  # Install PowerShell
  log INFO "Installing PowerShell..."
  wget -q https://packages.microsoft.com/config/ubuntu/22.04/packages-microsoft-prod.deb
  dpkg -i packages-microsoft-prod.deb || true
  rm -f packages-microsoft-prod.deb
  apt update -y
  apt install -y powershell || true
  log INFO "PowerShell installation complete."

  # Install Zig
  log INFO "Installing Zig..."
  ZIG_VERSION="zig-linux-x86_64-0.14.0-dev.2643+fb43e91b2"
  ZIG_URL="https://ziglang.org/builds/${ZIG_VERSION}.tar.xz"
  ZIG_TARBALL="/tmp/${ZIG_VERSION}.tar.xz"
  ZIG_EXTRACTED_DIR="/tmp/${ZIG_VERSION}"
  ZIG_INSTALL_DIR="/usr/local/zig"

  log INFO "Downloading Zig from $ZIG_URL..."
  wget -O "$ZIG_TARBALL" "$ZIG_URL"

  log INFO "Extracting Zig tarball..."
  tar xf "$ZIG_TARBALL" -C /tmp/

  if [[ ! -d "$ZIG_EXTRACTED_DIR" ]]; then
    log ERROR "Extraction failed: '$ZIG_EXTRACTED_DIR' does not exist!"
    exit 1
  fi

  log INFO "Installing Zig to $ZIG_INSTALL_DIR..."
  rm -rf "$ZIG_INSTALL_DIR"
  mv "$ZIG_EXTRACTED_DIR" "$ZIG_INSTALL_DIR"

  log INFO "Creating symlink for Zig binary..."
  ln -sf "$ZIG_INSTALL_DIR/zig" /usr/local/bin/zig
  chmod +x /usr/local/bin/zig

  log INFO "Cleaning up temporary files..."
  rm -f "$ZIG_TARBALL"

  log INFO "Zig installation complete."
}

################################################################################
# Function: Installs vscode cli
################################################################################
install_vscode_cli() {
  # Create a symbolic link for node to /usr/local/node
  log INFO "Creating symbolic link for Node.js..."
  if sudo ln -s "$(which node)" /usr/local/node; then
    log INFO "Symbolic link created at /usr/local/node."
  else
    log ERROR "Failed to create symbolic link for Node.js."
    return 1
  fi

  # Download the Visual Studio Code CLI for Alpine Linux
  log INFO "Downloading Visual Studio Code CLI..."
  if curl -Lk 'https://code.visualstudio.com/sha/download?build=stable&os=cli-alpine-x64' --output vscode_cli.tar.gz; then
    log INFO "Downloaded vscode_cli.tar.gz successfully."
  else
    log ERROR "Failed to download vscode_cli.tar.gz."
    return 1
  fi

  # Extract the downloaded tarball
  log INFO "Extracting vscode_cli.tar.gz..."
  if tar -xf vscode_cli.tar.gz; then
    log INFO "Extraction completed successfully."
  else
    log ERROR "Failed to extract vscode_cli.tar.gz."
    return 1
  fi

  log INFO "Visual Studio Code CLI installation steps completed."
  log INFO "Run './code tunnel --name ubuntu-server' from ~ to run the tunnel"
}

# ------------------------------------------------------------------------------
# MAIN FUNCTION: Installs Enlightenment Desktop and GUI
# ------------------------------------------------------------------------------
install_gui() {
  export DEBIAN_FRONTEND=noninteractive

  # Remove LightDM if installed to avoid configuration prompts
  if dpkg -l | grep -q lightdm; then
    log INFO "Removing LightDM to avoid configuration prompts..."
    apt-get remove --purge -y lightdm
  fi

  # Step 1: Installing git and Cloning
  log INFO "Installing Git..."
  apt-get update
  apt-get install -y git

  if [ -d "efl" ]; then
    log INFO "Repository 'efl' already exists. Pulling latest changes..."
    cd efl
    git pull
    cd ..
  else
    log INFO "Cloning the EFL repository..."
    git clone https://git.enlightenment.org/enlightenment/efl.git
  fi

  # Step 2: Installing Dependencies for EFL
  log INFO "Installing build tools and dependencies for EFL..."
  apt-get install -y build-essential check meson ninja-build

  apt-get install -y \
    libssl-dev libsystemd-dev libjpeg-dev libglib2.0-dev libgstreamer1.0-dev \
    liblua5.2-dev libfreetype-dev libfontconfig-dev libfribidi-dev \
    libavahi-client-dev libharfbuzz-dev libibus-1.0-dev libx11-dev libxext-dev \
    libxrender-dev libgl1-mesa-dev libgif-dev libtiff5-dev libpoppler-dev \
    libpoppler-cpp-dev libspectre-dev libraw-dev librsvg2-dev libudev-dev \
    libmount-dev libdbus-1-dev libpulse-dev libsndfile1-dev libxcursor-dev \
    libxcomposite-dev libxinerama-dev libxrandr-dev libxtst-dev libxss-dev \
    libgstreamer-plugins-base1.0-dev doxygen libopenjp2-7-dev libscim-dev \
    libxdamage-dev libwebp-dev libunwind-dev libheif-dev libavif-dev libyuv-dev \
    libinput-dev

  log INFO "Configuring, building, and installing EFL from source..."
  cd efl
  meson -Dlua-interpreter=lua build
  ninja -C build
  ninja -C build install
  cd ..

  log INFO "Updating PKG_CONFIG_PATH in /etc/profile..."
  local profile="/etc/profile"
  local pkg_config_line='export PKG_CONFIG_PATH=$PKG_CONFIG_PATH:/usr/local/lib/pkgconfig'
  if ! grep -Fxq "${pkg_config_line}" "${profile}"; then
    echo "${pkg_config_line}" | tee -a "${profile}" >/dev/null
  else
    log INFO "PKG_CONFIG_PATH line already present in ${profile}."
  fi

  log INFO "Refreshing library paths..."
  ldconfig

  log INFO "Installing Xorg, GDM3, and Enlightenment desktop environment..."
  apt-get install -y xorg gdm3 enlightenment

  log INFO "Enabling GDM3 for auto-start on boot..."
  systemctl enable gdm3

  log INFO "Installing backup desktop environments (XFCE, i3)..."
  apt-get install -y xfce4 i3 rofi i3lock i3blocks feh xterm alacritty ranger \
      network-manager network-manager-gnome pavucontrol alsa-utils picom \
      polybar fonts-powerline fonts-noto

  apt purge lightdm

  log INFO "Installing and enabling ConnMan service..."
  apt install -y connman
  systemctl enable connman

  log INFO "Full GDM/Enlightenment/i3/XFCE installation complete."
}

################################################################################
# Function: finalize_configuration
################################################################################
finalize_configuration() {
  log INFO "Finalizing system configuration..."

  # Add Flatpak remote flathub repository if not already added
  log INFO "Adding Flatpak flathub repository..."
  if flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo; then
    log INFO "Flathub repository added or already exists."
  else
    log ERROR "Failed to add Flathub repository."
  fi

  # Install GNOME Software and Flatpak plugin
  log INFO "Installing GNOME Software and Flatpak plugin..."
  if apt install -y gnome-software gnome-software-plugin-flatpak; then
    log INFO "GNOME Software and Flatpak plugin installed successfully."
  else
    log ERROR "Installation of GNOME Software and Flatpak plugin failed."
  fi

  # Update package list
  log INFO "Updating package list..."
  if apt update; then
    log INFO "Package list updated."
  else
    log ERROR "Failed to update package list."
  fi

  # Upgrade installed packages
  log INFO "Upgrading installed packages..."
  if apt upgrade -y; then
    log INFO "Packages upgraded."
  else
    log ERROR "Package upgrade failed."
  fi

  # Update Flatpak applications
  log INFO "Updating Flatpak applications..."
  if flatpak update -y; then
    log INFO "Flatpak applications updated."
  else
    log ERROR "Failed to update Flatpak applications."
  fi

  # Refresh Snap packages (if Snap is installed)
  log INFO "Refreshing Snap packages..."
  if command -v snap &>/dev/null; then
    if snap refresh; then
      log INFO "Snap packages refreshed."
    else
      log ERROR "Failed to refresh Snap packages."
    fi
  else
    log INFO "Snap is not installed; skipping Snap refresh."
  fi

  # Remove unused dependencies
  log INFO "Performing system cleanup..."
  if apt autoremove -y; then
    log INFO "Unused dependencies removed."
  else
    log ERROR "Failed to remove unused dependencies."
  fi

  # Clean up local package cache
  if apt clean; then
    log INFO "Package cache cleaned."
  else
    log ERROR "Failed to clean package cache."
  fi

  ##############################################################################
  # Additional System Logging Information
  ##############################################################################
  log INFO "Collecting system information..."

  # Uptime
  log INFO "System Uptime: $(uptime -p)"

  # Disk usage for root
  log INFO "Disk Usage (root): $(df -h / | tail -1)"

  # Memory usage
  log INFO "Memory Usage: $(free -h | grep Mem)"

  # CPU information
  CPU_MODEL=$(grep 'model name' /proc/cpuinfo | uniq | awk -F': ' '{print $2}')
  log INFO "CPU Model: ${CPU_MODEL:-Unknown}"

  # Kernel version
  log INFO "Kernel Version: $(uname -r)"

  # Network configuration
  log INFO "Network Configuration: $(ip addr show)"

  # End of system information collection
  log INFO "System information logged."

  log INFO "System configuration finalized."
}

################################################################################
# MAIN
################################################################################
main() {
  log INFO "--------------------------------------"
  log INFO "Starting Ubuntu Automated System Configuration Script"

# Bash script execution order:
  backup_system
  configure_ssh_settings
  force_release_ports
  configure_timezone "America/New_York"
  set_default_shell_and_env
  create_caddyfile
  bootstrap_and_install_pkgs
  configure_ufw
  configure_ntp
  fail2ban
  install_python_build_deps
  install_dev_build_deps
  install_apt_dependencies
  install_and_enable_plex
  install_powershell_and_zig
  download_repositories
  set_directory_permissions
  install_gui
  systemctl restart caddy
  install_vscode_cli
  finalize_configuration

  log INFO "Configuration script finished successfully."
  log INFO "Enjoy Ubuntu!!!"
  log INFO "--------------------------------------"
}

# Entrypoint
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
