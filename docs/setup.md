# Rebuilding the Pi from a blank card

Use this when the card dies, gets corrupted, or you need a second identical setup.
Target: about 20 minutes to a working, measured-identical platform.
Record anything that differs from the platform record in `plan.md` §4.3.

## 1. Flash the card (on the PC)

Raspberry Pi Imager (`rpi-imager`):

- **Device:** Raspberry Pi 4
- **OS:** Raspberry Pi OS (64-bit), the top entry (desktop image). Lite was tried and never joined the network; the desktop image is booted to console in step 5 instead.
- **Storage:** the SD card. Check the size; never the 2 TB or 1 TB drives.
- **Settings:** hostname `raspberry`, user `raspberry`, SSH enabled, time zone Asia/Riyadh. Wi-Fi is optional (see Known issues).

## 2. PC side of the direct Ethernet link (one-time; skip if already set up)

USB-C Ethernet adapter on the PC, cable to the Pi.

```fish
nmcli device                                   # adapter name, was enp113s0u1c2
nmcli connection add type ethernet ifname enp113s0u1c2 con-name pi-link ipv4.method shared ipv6.method link-local
nmcli connection up pi-link
sudo ufw allow in on enp113s0u1c2                       # DHCP/SSH from the Pi
sudo ufw route allow in on enp113s0u1c2 out on enp6s0   # Pi -> internet through the PC
```

If the Pi can ping the internet but `apt`/`curl` hang, Docker's FORWARD policy is also blocking. Add (not persistent across PC reboots):

```fish
sudo iptables -I DOCKER-USER -i enp113s0u1c2 -o enp6s0 -j ACCEPT
sudo iptables -I DOCKER-USER -i enp6s0 -o enp113s0u1c2 -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
```

**Undo everything on the PC:**

```fish
nmcli connection delete pi-link
sudo ufw delete allow in on enp113s0u1c2
sudo ufw route delete allow in on enp113s0u1c2 out on enp6s0
# and, if added: the same iptables lines with -D instead of -I
```

## 3. Connect

Power on the Pi, wait about 90 s.

```fish
sudo nmap -sn 10.42.0.0/24          # Pi shows as "Raspberry Pi Trading", usually 10.42.0.41
ssh-keygen -R 10.42.0.41            # new card = new host key
ssh raspberry@10.42.0.41
```

Test with `curl -sI http://deb.debian.org | head -1`, not ping: UFW forwards ICMP even when TCP is blocked.

## 4. Get the repo onto the Pi

The Pi uses its own SSH key, added to the GitHub repo as a **deploy key with write access**
(repo Settings → Deploy keys), so it can push results without access to anything else.

```sh
ssh-keygen -t ed25519 -C "ee654-pi" -N "" -f ~/.ssh/id_ed25519
cat ~/.ssh/id_ed25519.pub           # paste into GitHub → repo → Settings → Deploy keys (tick "Allow write access")
ssh -T git@github.com               # should greet the repo name
git config --global user.name  "Yazeed (Pi)"
git config --global user.email "<your GitHub email>"
git clone git@github.com:<your-user>/ee654-pi-energy.git
cd ee654-pi-energy
```

On a rebuild, the old deploy key is gone with the card: delete it on GitHub and add the new one.

## 5. Configure

```sh
sudo ./scripts/setup_pi.sh --upgrade   # first build only; omit --upgrade during the measurement phase
sudo reboot
```

## 6. Verify

```sh
./scripts/sysinfo.sh
```

Compare kernel, EEPROM, ffmpeg, boot target and held packages with `plan.md` §4.3.
If anything differs, write it in the results log before measuring.

## 7. Image the finished card (on the PC)

Shut the Pi down (`sudo poweroff`), move the card to the reader:

```fish
lsblk -f                              # find the card, e.g. /dev/sdc
./scripts/backup_card.sh /dev/sdc     # writes ~/pi-backups/pi-card-<date>.img.zst
```

Restoring that image is faster than steps 1–6 and gives a bit-identical system.

## Known issues

- **Wi-Fi does not join** on recent flashes (Imager credentials). Unresolved; the wired link is used instead. If fixed, keep Wi-Fi **off** during measurements (`sudo nmcli radio wifi off`) so the radio is not a variable.
- **apt tries IPv6 and fails** over the shared link: handled by `/etc/apt/apt.conf.d/99force-ipv4` (set by `setup_pi.sh`).
- **Pi never gets an address:** PC firewall blocking DHCP on the adapter (step 2, first UFW rule).
