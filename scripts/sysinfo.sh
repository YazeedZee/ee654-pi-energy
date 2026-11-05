#!/usr/bin/env bash
# Capture the Pi's platform state (OS, kernel, firmware, CPU frequency setup, thermal state).
# Usage: ./scripts/sysinfo.sh [output-file]
# Default output: data/raw/sysinfo/sysinfo-<host>-<timestamp>.txt
# Every experiment calls this so each dataset carries the exact platform it ran on.
set -uo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$REPO_DIR/data/raw/sysinfo/sysinfo-$(hostname)-$(date +%Y%m%dT%H%M%S).txt}"
mkdir -p "$(dirname "$OUT")"
CPUFREQ=/sys/devices/system/cpu/cpu0/cpufreq

section() { printf '\n## %s\n' "$1"; }
show()    { section "$1"; shift; "$@" 2>&1 || echo "(unavailable)"; }

{
  echo "# sysinfo captured $(date --iso-8601=seconds) on $(hostname)"
  show "OS image"            cat /boot/firmware/issue.txt
  show "os-release"          grep -E '^(PRETTY_NAME|VERSION_ID)=' /etc/os-release
  show "Kernel"              uname -a
  show "Board"               grep -E 'Model|Revision' /proc/cpuinfo
  show "Memory"              free -h
  show "Bootloader EEPROM"   vcgencmd bootloader_version
  show "Firmware"            vcgencmd version
  show "Boot target"         systemctl get-default
  show "Held packages"       apt-mark showhold
  show "ffmpeg"              sh -c 'ffmpeg -version | head -1'
  show "Governor"            cat $CPUFREQ/scaling_governor
  show "Available governors" cat $CPUFREQ/scaling_available_governors
  show "Available freqs kHz" cat $CPUFREQ/scaling_available_frequencies
  show "Current freq kHz"    cat $CPUFREQ/scaling_cur_freq
  show "Freq limits kHz"     sh -c "echo min=\$(cat $CPUFREQ/scaling_min_freq) max=\$(cat $CPUFREQ/scaling_max_freq)"
  show "Core voltage"        vcgencmd measure_volts core
  show "Temperature"         vcgencmd measure_temp
  show "Throttled flags"     vcgencmd get_throttled
  show "Root filesystem"     df -h /
  show "SD card"             sh -c 'echo "name=$(cat /sys/block/mmcblk0/device/name) size=$(lsblk -dno SIZE /dev/mmcblk0)"'
  show "Network"             ip -br addr
  show "Running services"    systemctl list-units --type=service --state=running --no-legend --plain
  show "Load"                cat /proc/loadavg
} > "$OUT"

echo "$OUT"
