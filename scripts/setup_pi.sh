#!/usr/bin/env bash
# Rebuild the experiment environment on a freshly flashed Raspberry Pi OS (64-bit) card.
# Safe to re-run. Run on the Pi, from the repo root:
#   sudo ./scripts/setup_pi.sh            # configure + install, no system upgrade
#   sudo ./scripts/setup_pi.sh --upgrade  # also run apt full-upgrade (only BEFORE measurements start)
# See docs/setup.md for the full rebuild procedure.
set -euo pipefail

[[ $EUID -eq 0 ]] || { echo "Run with sudo."; exit 1; }
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
USER_NAME="${SUDO_USER:-raspberry}"

echo "== apt: use IPv4 only (the PC's shared link provides IPv4 only)"
echo 'Acquire::ForceIPv4 "true";' > /etc/apt/apt.conf.d/99force-ipv4

echo "== boot to console (no graphical session)"
systemctl set-default multi-user.target

echo "== disable services not needed for the study"
for s in cups cups-browsed bluetooth ModemManager; do
  if systemctl list-unit-files "$s.service" --no-legend | grep -q .; then
    systemctl disable --now "$s" >/dev/null 2>&1 && echo "   disabled $s"
  else
    echo "   $s not installed"
  fi
done

echo "== packages"
apt-get update
if [[ "${1:-}" == "--upgrade" ]]; then
  echo "   full-upgrade requested"
  apt-get full-upgrade -y
fi
apt-get install -y ffmpeg git rsync stress-ng htop python3-numpy python3-pandas

echo "== freeze bootloader firmware updates for the study"
apt-mark hold rpi-eeprom

echo "== record platform state"
sudo -u "$USER_NAME" "$REPO_DIR/scripts/sysinfo.sh"

echo
echo "Done. Reboot to apply the boot target:  sudo reboot"
echo "Then compare the sysinfo file above with docs/plan.md section 4.3."
