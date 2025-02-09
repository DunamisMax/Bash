#!/usr/bin/env bash
# ------------------------------------------------------------------------------
# Script Name: vm_manager.sh
# Description: An advanced interactive virtual machine manager that allows you
#              to list, create, start, stop, delete, and monitor KVM/QEMU virtual
#              machines on Ubuntu. The script uses virt‑install and virsh, and
#              walks you through VM creation (including options for RAM, vCPUs,
#              disk size, and ISO download via wget) in a fully interactive, 
#              Nord‑themed interface.
#
# Author: Your Name | License: MIT
# Version: 2.0
# ------------------------------------------------------------------------------
#
# Usage:
#   sudo ./advanced_vm_manager.sh
#
# ------------------------------------------------------------------------------
# ENABLE STRICT MODE
set -Eeuo pipefail
trap 'echo -e "\n${NORD11}An error occurred at line ${LINENO}.${NC}" >&2; exit 1' ERR
trap 'echo -e "\n${NORD11}Operation interrupted. Returning to main menu...${NC}"' SIGINT

# ------------------------------------------------------------------------------
# Nord Color Theme Constants (24‑bit ANSI escapes)
# ------------------------------------------------------------------------------
NORD0='\033[38;2;46;52;64m'      # Dark background
NORD1='\033[38;2;59;66;82m'
NORD2='\033[38;2;67;76;94m'
NORD3='\033[38;2;76;86;106m'
NORD4='\033[38;2;216;222;233m'   # Light Gray (text)
NORD7='\033[38;2;143;188;187m'   # Teal (success/info)
NORD8='\033[38;2;136;192;208m'   # Accent Blue (headings)
NORD11='\033[38;2;191;97;106m'   # Red (errors)
NORD12='\033[38;2;208;135;112m'  # Orange (warnings)
NORD14='\033[38;2;163;190;140m'  # Green (labels/values)
NC='\033[0m'                    # No Color

# ------------------------------------------------------------------------------
# Global Variables
# ------------------------------------------------------------------------------
VM_IMAGE_DIR="/var/lib/libvirt/images"   # Default location for VM disk images
ISO_DIR="/var/lib/libvirt/boot"            # Directory to store downloaded ISOs
mkdir -p "$ISO_DIR"
TMP_ISO="/tmp/vm_install.iso"              # Temporary ISO download location

# ------------------------------------------------------------------------------
# Helper Functions
# ------------------------------------------------------------------------------
print_header() {
    clear
    echo -e "${NORD8}============================================${NC}"
    echo -e "${NORD8}       Advanced VM Manager Tool             ${NC}"
    echo -e "${NORD8}============================================${NC}"
}

print_divider() {
    echo -e "${NORD8}--------------------------------------------${NC}"
}

progress_bar() {
    # Usage: progress_bar "Message" duration_in_seconds
    local message="$1"
    local duration="${2:-3}"
    local steps=50
    local sleep_time
    sleep_time=$(echo "$duration / $steps" | bc -l)
    printf "\n${NORD8}%s [" "$message"
    for ((i=1; i<=steps; i++)); do
        printf "█"
        sleep "$sleep_time"
    done
    printf "]${NC}\n"
}

prompt_enter() {
    read -rp "Press Enter to continue..." dummy
}

# ------------------------------------------------------------------------------
# VM Management Functions
# ------------------------------------------------------------------------------
list_vms() {
    print_header
    echo -e "${NORD14}Current Virtual Machines:${NC}"
    print_divider
    # List all VMs (running and stopped)
    virsh list --all
    print_divider
    prompt_enter
}

start_vm() {
    print_header
    echo -e "${NORD14}Start a Virtual Machine:${NC}"
    list_vms
    read -rp "Enter the VM name to start: " vm_name
    if virsh start "$vm_name"; then
        echo -e "${NORD14}VM '$vm_name' started successfully.${NC}"
    else
        echo -e "${NORD11}Failed to start VM '$vm_name'.${NC}"
    fi
    prompt_enter
}

stop_vm() {
    print_header
    echo -e "${NORD14}Stop a Virtual Machine:${NC}"
    list_vms
    read -rp "Enter the VM name to stop (graceful shutdown): " vm_name
    if virsh shutdown "$vm_name"; then
        echo -e "${NORD14}Shutdown signal sent to VM '$vm_name'.${NC}"
    else
        echo -e "${NORD11}Failed to shutdown VM '$vm_name'.${NC}"
    fi
    prompt_enter
}

delete_vm() {
    print_header
    echo -e "${NORD14}Delete a Virtual Machine:${NC}"
    list_vms
    read -rp "Enter the VM name to delete: " vm_name
    read -rp "Are you sure you want to delete VM '$vm_name'? This will undefine the VM. (y/n): " confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        echo -e "${NORD12}Deletion cancelled.${NC}"
        prompt_enter
        return 0
    fi

    # If the VM is running, force shutdown first.
    if virsh list --state-running | grep -q "$vm_name"; then
        virsh destroy "$vm_name"
    fi
    if virsh undefine "$vm_name"; then
        echo -e "${NORD14}VM '$vm_name' undefined successfully.${NC}"
        read -rp "Do you want to remove its disk image? (y/n): " remove_disk
        if [[ "$remove_disk" =~ ^[Yy]$ ]]; then
            local disk
            # Retrieve disk path from VM XML definition if available
            disk=$(virsh dumpxml "$vm_name" | grep -oP 'source file="\K[^"]+')
            if [[ -n "$disk" && -f "$disk" ]]; then
                rm -f "$disk" && echo -e "${NORD14}Disk image removed.${NC}"
            else
                echo -e "${NORD12}Disk image not found or already removed.${NC}"
            fi
        fi
    else
        echo -e "${NORD11}Failed to delete VM '$vm_name'.${NC}"
    fi
    prompt_enter
}

monitor_vm() {
    print_header
    echo -e "${NORD14}Monitor Virtual Machine Resource Usage:${NC}"
    list_vms
    read -rp "Enter the VM name to monitor: " vm_name
    echo -e "${NORD14}Press Ctrl+C to exit monitoring and return to the menu.${NC}"
    while true; do
        clear
        echo -e "${NORD8}Monitoring VM: ${NORD4}${vm_name}${NC}"
        echo -e "${NORD8}--------------------------------------------${NC}"
        virsh dominfo "$vm_name"
        echo -e "${NORD8}--------------------------------------------${NC}"
        sleep 5
    done
}

download_iso() {
    read -rp "Enter the URL for the installation ISO: " iso_url
    read -rp "Enter the desired filename (e.g., ubuntu.iso): " iso_filename
    local iso_path="${ISO_DIR}/${iso_filename}"
    echo -e "${NORD14}Downloading ISO to ${iso_path}...${NC}"
    progress_bar "Downloading ISO" 10
    if wget -O "$iso_path" "$iso_url"; then
        echo -e "${NORD14}ISO downloaded successfully.${NC}"
        echo "$iso_path"
    else
        echo -e "${NORD11}Failed to download ISO.${NC}"
        return 1
    fi
}

create_vm() {
    print_header
    echo -e "${NORD14}Create a New Virtual Machine:${NC}"
    read -rp "Enter VM name: " vm_name
    read -rp "Enter number of vCPUs: " vcpus
    read -rp "Enter RAM in MB: " ram
    read -rp "Enter disk size in GB: " disk_size

    # Ask user for ISO location
    echo -e "${NORD14}Provide installation ISO:${NC}"
    echo -e "${NORD8}[1]${NC} Use existing ISO file"
    echo -e "${NORD8}[2]${NC} Download ISO via URL (wget)"
    read -rp "Enter your choice (1 or 2): " iso_choice
    local iso_path=""
    case "$iso_choice" in
        1)
            read -rp "Enter full path to ISO file: " iso_path
            if [[ ! -f "$iso_path" ]]; then
                echo -e "${NORD11}ISO file not found at $iso_path.${NC}"
                prompt_enter
                return 1
            fi
            ;;
        2)
            iso_path=$(download_iso) || return 1
            ;;
        *)
            echo -e "${NORD12}Invalid selection. Cancelling VM creation.${NC}"
            prompt_enter
            return 1
            ;;
    esac

    # Create a disk image for the VM.
    local disk_image="${VM_IMAGE_DIR}/${vm_name}.qcow2"
    echo -e "${NORD14}Creating disk image at ${disk_image}...${NC}"
    progress_bar "Creating disk image" 5
    if ! qemu-img create -f qcow2 "$disk_image" "${disk_size}G"; then
        echo -e "${NORD11}Failed to create disk image.${NC}"
        prompt_enter
        return 1
    fi

    # Use virt-install to create the VM.
    echo -e "${NORD14}Starting VM installation using virt-install...${NC}"
    progress_bar "Launching virt-install" 5
    virt-install --name "$vm_name" \
        --ram "$ram" \
        --vcpus "$vcpus" \
        --disk path="$disk_image",size="$disk_size",format=qcow2 \
        --cdrom "$iso_path" \
        --os-type linux \
        --os-variant ubuntu20.04 \
        --graphics none \
        --console pty,target_type=serial \
        --noautoconsole

    if [[ $? -eq 0 ]]; then
        echo -e "${NORD14}VM '$vm_name' created successfully.${NC}"
    else
        echo -e "${NORD11}Failed to create VM '$vm_name'.${NC}"
    fi
    prompt_enter
}

# ------------------------------------------------------------------------------
# Main Interactive Menu
# ------------------------------------------------------------------------------
main_menu() {
    while true; do
        print_header
        echo -e "${NORD14}[1]${NC} List Virtual Machines"
        echo -e "${NORD14}[2]${NC} Create Virtual Machine"
        echo -e "${NORD14}[3]${NC} Start Virtual Machine"
        echo -e "${NORD14}[4]${NC} Stop Virtual Machine"
        echo -e "${NORD14}[5]${NC} Delete Virtual Machine"
        echo -e "${NORD14}[6]${NC} Monitor Virtual Machine Resources"
        echo -e "${NORD14}[q]${NC} Quit"
        print_divider
        read -rp "Enter your choice: " choice
        case "${choice,,}" in
            1)
                list_vms
                ;;
            2)
                create_vm
                ;;
            3)
                start_vm
                ;;
            4)
                stop_vm
                ;;
            5)
                delete_vm
                ;;
            6)
                monitor_vm
                ;;
            q)
                echo -e "${NORD14}Goodbye!${NC}"
                exit 0
                ;;
            *)
                echo -e "${NORD12}Invalid selection. Please try again.${NC}"
                sleep 1
                ;;
        esac
    done
}

# ------------------------------------------------------------------------------
# Main Entry Point
# ------------------------------------------------------------------------------
main() {
    # Ensure required commands exist
    for cmd in virsh virt-install qemu-img wget; do
        if ! command -v "$cmd" &>/dev/null; then
            echo -e "${NORD11}Error: Required command '$cmd' is not installed. Exiting.${NC}"
            exit 1
        fi
    done

    main_menu
}

# ------------------------------------------------------------------------------
# Execute Main if Script is Run Directly
# ------------------------------------------------------------------------------
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    main "$@"
fi