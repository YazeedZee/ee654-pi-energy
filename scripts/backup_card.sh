#!/usr/bin/env bash
# Make a compressed image of the Pi's SD card. Run on the PC with the card in a USB reader.
# Only READS the card. Refuses anything that does not look like an SD card.
# Usage: ./scripts/backup_card.sh /dev/sdX [output-dir]
set -euo pipefail

DEV="${1:?usage: $0 /dev/sdX [output-dir]   (check the device with: lsblk -f)}"
OUTDIR="${2:-$HOME/pi-backups}"
MAX_BYTES=$((256 * 1024 * 1024 * 1024))   # refuse anything larger than 256 GiB

command -v zstd >/dev/null || { echo "zstd not installed (sudo pacman -S zstd)"; exit 1; }
[[ -b "$DEV" ]] || { echo "$DEV is not a block device."; exit 1; }
[[ "$(lsblk -dno TYPE "$DEV")" == "disk" ]] || { echo "Give the whole disk (e.g. /dev/sdc), not a partition."; exit 1; }

SIZE=$(lsblk -dbno SIZE "$DEV")
RM=$(lsblk -dno RM "$DEV" | tr -d ' ')
TRAN=$(lsblk -dno TRAN "$DEV" | tr -d ' ')
if (( SIZE > MAX_BYTES )); then
  echo "Refusing: $DEV is $(lsblk -dno SIZE "$DEV"), too large to be the Pi's SD card."; exit 1
fi
if [[ "$RM" != "1" && "$TRAN" != "usb" ]]; then
  echo "Refusing: $DEV is neither removable nor USB-attached."; exit 1
fi
if ! lsblk -no LABEL "$DEV" | grep -qx 'bootfs\|boot'; then
  echo "Warning: no 'bootfs' partition found on $DEV. This may not be a Raspberry Pi OS card."
fi

echo
lsblk -o NAME,SIZE,FSTYPE,LABEL,MOUNTPOINTS "$DEV"
echo
read -rp "Image $DEV ($(lsblk -dno SIZE "$DEV")) to $OUTDIR? Type 'yes': " ok
[[ "$ok" == "yes" ]] || { echo "Cancelled."; exit 1; }

# Unmount any mounted partitions so the image is consistent
for p in $(lsblk -lnpo NAME "$DEV" | tail -n +2); do
  if findmnt -rn -S "$p" >/dev/null; then
    udisksctl unmount -b "$p" >/dev/null 2>&1 || sudo umount "$p"
    echo "unmounted $p"
  fi
done

mkdir -p "$OUTDIR"
OUT="$OUTDIR/pi-card-$(date +%Y%m%d-%H%M).img.zst"
sudo dd if="$DEV" bs=4M status=progress conv=fsync | zstd -T0 -q -o "$OUT"
sha256sum "$OUT" > "$OUT.sha256"

echo
echo "Saved: $OUT ($(du -h "$OUT" | cut -f1))"
echo "Restore (OVERWRITES the target card, check the device first):"
echo "  zstd -dc $OUT | sudo dd of=/dev/sdX bs=4M status=progress conv=fsync"
