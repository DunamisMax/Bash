#!/usr/bin/env bash
set -euo pipefail
USERNAME="sawyer"

check_root() {
  [ "$(id -u)" -eq 0 ] || { echo "Run as root"; exit 1; }
}

check_network() {
  ping -c1 -W5 google.com >/dev/null || { echo "No network connectivity"; exit 1; }
}

update_system() {
  apk update && apk upgrade
}

install_packages() {
  apk add --no-cache \
    bash vim nano screen tmux mc build-base cmake ninja meson gettext git \
    openssh curl wget rsync htop sudo python3 py3-pip tzdata iptables \
    ca-certificates bash-completion openrc
}

create_user() {
  if ! id -u "$USERNAME" >/dev/null 2>&1; then
    adduser "$USERNAME"
    passwd "$USERNAME"
    echo "$USERNAME ALL=(ALL) ALL" >> /etc/sudoers
  fi
}

configure_timezone() {
  cp /usr/share/zoneinfo/America/New_York /etc/localtime || true
  echo "America/New_York" > /etc/timezone
}

setup_repos() {
  mkdir -p /home/${USERNAME}/github
  for repo in bash windows web python go misc; do
    rm -rf /home/${USERNAME}/github/$repo
    git clone "https://github.com/dunamismax/$repo.git" /home/${USERNAME}/github/$repo || true
  done
  chown -R ${USERNAME}:${USERNAME} /home/${USERNAME}/github
}

copy_shell_configs() {
  for file in .bashrc .profile; do
    cp -f /home/${USERNAME}/github/bash/linux/dotfiles/$file /home/${USERNAME}/ 2>/dev/null || true
  done
}

configure_ssh() {
  # Make sure openrc is set up
  if [ ! -f /sbin/openrc-run ]; then
    echo "OpenRC not found. Installing openrc..."
    apk add --no-cache openrc
  fi
  rc-update add sshd default || true
  rc-service sshd stop 2>/dev/null || true
  rc-service sshd start
}

install_zig_binary() {
  apk add --no-cache curl tar
  rm -rf /opt/zig
  mkdir -p /opt/zig
  curl -L -o /tmp/zig.tar.xz https://ziglang.org/download/0.12.1/zig-linux-armv7a-0.12.1.tar.xz
  tar -xf /tmp/zig.tar.xz -C /opt/zig --strip-components=1
  ln -sf /opt/zig/zig /usr/local/bin/zig
  rm -f /tmp/zig.tar.xz
  zig version >/dev/null || { echo "Zig installation failed"; exit 1; }
}

configure_firewall() {
  iptables -P INPUT DROP
  iptables -P FORWARD DROP
  iptables -P OUTPUT ACCEPT
  iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
  iptables -A INPUT -i lo -j ACCEPT
  iptables -A INPUT -p icmp -j ACCEPT
  iptables -A INPUT -p tcp --dport 22 -j ACCEPT
  iptables -A INPUT -p tcp --dport 80 -j ACCEPT
  iptables -A INPUT -p tcp --dport 443 -j ACCEPT
  iptables -A INPUT -p tcp --dport 32400 -j ACCEPT
}

deploy_user_scripts() {
  mkdir -p /home/${USERNAME}/bin
  rsync -ah --delete /home/${USERNAME}/github/bash/linux/_scripts/ /home/${USERNAME}/bin/ 2>/dev/null || true
  find /home/${USERNAME}/bin -type f -exec chmod 755 {} \;
}

setup_cron() {
  rc-update add crond default || true
  rc-service crond start
}

final_checks() {
  echo "Kernel: $(uname -r)"
  echo "Uptime: $(uptime -p)"
  df -h /
  free -h
}

home_permissions() {
  chown -R ${USERNAME}:${USERNAME} /home/${USERNAME}
  find /home/${USERNAME} -type d -exec chmod g+s {} \; 2>/dev/null || true
}

dotfiles_load() {
  mkdir -p \
    /home/${USERNAME}/.config/alacritty \
    /home/${USERNAME}/.config/i3 \
    /home/${USERNAME}/.config/i3blocks \
    /home/${USERNAME}/.config/picom
  rsync -a --delete /home/${USERNAME}/github/bash/linux/dotfiles/alacritty/ /home/${USERNAME}/.config/alacritty/ 2>/dev/null || true
  rsync -a --delete /home/${USERNAME}/github/bash/linux/dotfiles/i3/ /home/${USERNAME}/.config/i3/ 2>/dev/null || true
  rsync -a --delete /home/${USERNAME}/github/bash/linux/dotfiles/i3blocks/ /home/${USERNAME}/.config/i3blocks/ 2>/dev/null || true
  chmod -R +x /home/${USERNAME}/.config/i3blocks/scripts 2>/dev/null || true
  rsync -a --delete /home/${USERNAME}/github/bash/linux/dotfiles/picom/ /home/${USERNAME}/.config/picom/ 2>/dev/null || true
}

cleanup() {
  echo "Cleanup tasks complete."
}

prompt_reboot() {
  read -p "Reboot now? [y/N]: " ans
  echo "$ans" | grep -qi "^y" && reboot
}

main() {
  check_root
  check_network
  update_system
  install_packages
  create_user
  configure_timezone
  setup_repos
  copy_shell_configs
  configure_ssh
  install_zig_binary
  configure_firewall
  deploy_user_scripts
  setup_cron
  final_checks
  home_permissions
  dotfiles_load
  cleanup
  prompt_reboot
}

main "$@"