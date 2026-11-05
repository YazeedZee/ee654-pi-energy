# EE654 Project: Energy vs. Deadlines in a Video Pipeline on Raspberry Pi 4 (v0.8)

**Course:** EE654 Embedded and Real-Time Systems, King Abdulaziz University (Fall 2026)
**Platform:** Raspberry Pi 4
**Status:** Setup / pre-baseline
**Working title:** *Is Slowing Down Worth It? Testing Energy-Saving Assumptions for a Soft Real-Time Video Pipeline on the Raspberry Pi 4*

---

## 1. One-sentence summary

A video pipeline must finish every frame before a deadline (≈33 ms at 30 FPS). This project measures **how to meet that deadline with the least energy**, using three controls: *where* each stage runs (CPU, GPU, hardware codec), *how fast* the CPU runs (frequency scaling), and *how* stages are scheduled (Linux schedulers). It compares what scheduling and DVFS theory predicts against what the hardware actually does.

**Contribution type:** mainly a measurement study, plus a small technique (a slack-based frequency controller).

---

## 2. Research questions

| ID | Question | Role in paper |
|---|---|---|
| **RQ2** | Does lowering the CPU frequency save as much energy as DVFS theory predicts? | **Main question** |
| RQ1 | Does offloading encode/decode to the hardware codec save energy, and does frame copying cancel the benefit? | Supporting |
| RQ3 | Which scheduler best protects frame deadlines under background load? | Supporting |

### RQ2: DVFS assumptions (main)
- **Policies compared:** `performance`, `ondemand`, `schedutil`, race-to-idle, custom slack-based controller.
- **Hypothesis H2a:** Execution time scales as 1/f for CPU-bound stages (detection) but *not* for memory-bound stages (decode, copies).
- **Hypothesis H2b:** Because a large share of board power is fixed, race-to-idle matches or beats running slower.
- **Assumption under test:** classic DVFS models (e.g., Pillai & Shin 2001) assume C(f) ∝ 1/f.
- **Either outcome is a result:**
  - If H2a holds → standard models misjudge slowdown and savings for memory-bound stages.
  - If everything scales as 1/f → model holds on this platform; focus shifts to the controller's actual gains.

### RQ1: Offloading
- **Configurations:** CPU (`libx264`) vs. hardware codec (`h264_v4l2m2m`); frame transfer by copy vs. zero-copy (dmabuf).
- **Hypothesis H1:** Hardware offload saves significant energy only with zero-copy; at 1080p, copies eat most of the benefit.

### RQ3: Scheduling
- **Schedulers:** CFS (default), `SCHED_FIFO` with pinned cores (partitioned fixed-priority / RMS-style), `SCHED_DEADLINE` (global EDF).
- **Background load:** `stress-ng`.
- **Hypothesis H3:** Similar averages; under load, CFS has a much worse latency tail.
- **Extra question:** Since `schedutil` reads `SCHED_DEADLINE` reserved bandwidth when choosing frequency, does reserving the right CPU time with EDF give near-optimal energy without a custom controller?

---

## 3. System model (what the results assume)

- **Pipeline:** decode → preprocess → detect → overlay → encode.
- **Task model:** each stage is a task; frame period T = 33.3 ms (30 FPS); end-to-end deadline D = T (also test D < T if time allows).
- **Real-time class:** soft real-time. Claims are about deadline-miss ratio and latency tail, **not** guarantees.
- **Platform facts that shape the design:**
  - All four Cortex-A72 cores share **one clock**, so no per-core DVFS.
  - 13 frequency steps: 600–1800 MHz in 100 MHz increments. Core voltage is set by firmware, so not every step lowers voltage; voltage per step must be measured (`vcgencmd measure_volts core`).
  - Thermal throttling around 80 °C, so temperature must be controlled and logged.
  - No on-board power telemetry on Pi 4; power is measured externally.
- **Input:** pre-recorded video files (repeatable), at least 2 resolutions × 2 motion levels.

---

## 4. Hardware

### 4.1 Available now
| Item | Use | Notes |
|---|---|---|
| Raspberry Pi 4 | Device under test | Check RAM size and board revision (`cat /proc/cpuinfo`) |
| Heatsinks (CPU, RAM) | Thermal control | Fine, but not enough alone under sustained load |
| Small fan (from kit) | Thermal control | **Required** for all runs; keep it at a constant speed |
| Wall-plug inline power meter | Coarse power reading | See limitations in 4.2 |
| UART adapters | Debug console; future STM32 link | Not needed for phase 1 |

### 4.2 Gap: power measurement
The wall-plug meter is usable for an early sanity check, but **not good enough for the paper's main evidence**:
- It measures **AC power before the Pi's power supply**, so supply conversion losses are mixed into every reading.
- It typically updates about once per second, with ~0.1 W resolution, and most models **don't log**.
- It can't give per-frame or per-stage energy, which RQ2 needs.

**Upgrade options (pick one):**
1. **USB-C power tester with PC logging** (FNB58-class): cheapest step up. Measures the 5 V side and logs to a PC. Good for energy per run.
2. **INA226 breakout on the 5 V line, logged by a separate microcontroller** (e.g., an STM32F4): best option. High sample rate, plus the Pi can toggle a GPIO at each frame boundary so energy can be split **per frame**. Uses the UART adapters to stream data to a PC.

**Also useful:** a cheap USB logic analyzer (for timing frame markers), and a good-quality microSD card (slow cards distort I/O timing).

### 4.3 Platform record (as installed)
Keep this table current; it becomes the paper's setup section.

| Item | Value | How to check |
|---|---|---|
| OS image | Raspberry Pi OS reference **2026-10-06** (pi-gen `b2cd98a`, **stage4 = full desktop image**) | `cat /boot/firmware/issue.txt` |
| Architecture | aarch64 (64-bit) | `uname -m` |
| Kernel | `6.18.60+rpt-rpi-v8` (Debian `1:6.18.60-1+rpt1`, built 2026-11-03), after one-time `full-upgrade` on 2026-11-05 (was 6.18.50) | `uname -a` |
| Boot target | `multi-user.target` (console, no graphical session) | `systemctl get-default` |
| Preemption model | `PREEMPT` (fully preemptible), **not** PREEMPT_RT | `uname -a` |
| Hostname / user | `raspberry` / `raspberry` | — |
| OS base | Debian 13 (trixie), from package versions | `cat /etc/os-release` |
| Board revision, RAM | Pi 4 Model B **Rev 1.4** (`c03114`), **4 GB** | `grep -E 'Model\|Revision' /proc/cpuinfo`; `free -h` |
| Bootloader (EEPROM) | **2026-09-23** (`456428d`), updated 2026-11-03 from 2021-04-29 (`c2f8c38`); VL805 USB firmware `000138a1` | `vcgencmd bootloader_version` |
| CPU frequency steps | 600–1800 MHz, 100 MHz steps (13 levels) | `cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_frequencies` |
| Available governors | conservative, ondemand, userspace, powersave, performance, schedutil | `cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors` |
| ffmpeg version | 7.1.5 (`7.1.5-0+deb13u1+rpt2`) | `ffmpeg -version \| head -1` |
| HW codec devices | V4L2 M2M nodes `/dev/video10–23, 31`; ffmpeg lists `h264_v4l2m2m` encoder and decoder. ffmpeg also lists wrappers the Pi 4 has no hardware for (e.g. HEVC/VP8 encode), so a functional test is required | `ls /dev/video*`; `ffmpeg -encoders \| grep v4l2m2m` |
| Core voltage per frequency | *TBD* | set each frequency via `userspace` governor, then `vcgencmd measure_volts core` |
| Storage | microSD, *model/size TBD* | — |
| Management link | Direct Ethernet: PC USB-C adapter (`enp113s0u1c2`), NetworkManager "shared" mode, PC `10.42.0.1`, Pi `10.42.0.41`. PC firewall rules: `ufw allow in on enp113s0u1c2` and `ufw route allow in on enp113s0u1c2 out on enp6s0` (undo: `ufw delete allow in on enp113s0u1c2`; `ufw route delete allow in on enp113s0u1c2 out on enp6s0`). Docker `DOCKER-USER` rules: *record if added*. Pi apt forced to IPv4 (`/etc/apt/apt.conf.d/99force-ipv4`) | `nmcli connection show pi-link` |

**Note:** the full desktop image is used, booted to console (`multi-user.target`) with non-essential services disabled; Lite was tried and never joined the network. Idle load is to be measured and reported.

---

## 5. Software stack (planned)

- Raspberry Pi OS 64-bit, desktop image booted to console (headless), configured by `scripts/setup_pi.sh`
- ffmpeg with V4L2 M2M support (hardware codec)
- Detector: OpenCV DNN or TFLite (small model, e.g., MobileNet-SSD class)
- `cpufreq` governors + `userspace` governor for the custom controller
- `chrt` / `sched_setattr` for `SCHED_FIFO` and `SCHED_DEADLINE`; `taskset` / cpusets for pinning
- PREEMPT_RT kernel (optional, phase 3)
- `stress-ng` for background load
- Logging: per-frame timestamps (CLOCK_MONOTONIC), `vcgencmd measure_temp`, `vcgencmd get_throttled`, `scaling_cur_freq`
- Analysis: Python (pandas, matplotlib)

---

## 6. Experimental design

### 6.1 Factors
| Factor | Levels |
|---|---|
| Resolution | 720p, 1080p |
| Video content | Low motion, high motion |
| Codec placement | CPU, HW codec (copy), HW codec (zero-copy) |
| Frequency policy | performance, ondemand, schedutil, race-to-idle, slack controller, fixed frequencies |
| Scheduler | CFS, SCHED_FIFO pinned, SCHED_DEADLINE |
| Background load | none, stress-ng |

Not every combination will be run. RQ2 varies frequency policy with other factors fixed at a reference setting; RQ1 and RQ3 likewise.

### 6.2 Metrics
- **Energy per frame** (J), computed by integrating power over the run and dividing by frames. **Not** average watts alone.
- **Deadline-miss ratio** (% of frames with latency > D).
- **Frame latency:** median, p99, maximum. Not mean ± SD.
- **Per-stage execution time at each frequency** → C_i(f) table.
- CPU frequency over time, die temperature, throttle flags.

### 6.3 Statistics
- At least 10 runs × ~3 minutes per configuration, after warm-up.
- Report medians with confidence intervals; percentiles for latency.
- Use non-parametric tests (e.g., Mann–Whitney) where distributions are skewed.

### 6.4 Controls (one per likely reviewer question)
- [ ] Fan on, constant; temperature and throttle flags logged every run
- [ ] Same input files, same build, same compiler flags across configurations
- [ ] Warm-up period discarded
- [ ] HDMI, Wi-Fi, Bluetooth, USB devices in the same state every run (ideally disabled)
- [ ] Same power supply and cable throughout
- [ ] Frequency-switching latency measured and reported

### 6.5 Analysis-vs.-reality step
1. Measure C_i(f) for each stage at each frequency.
2. Use utilization / response-time analysis to **predict** the lowest frequency that meets D, and the energy it should save.
3. Run it and **measure**.
4. Explain the gap: memory-bound stages, fixed board power, switching overhead.

---

## 7. Week-one feasibility test

**Goal:** confirm a paper exists here before committing.

1. Install OS, ffmpeg, detector; build the minimal pipeline on one video file.
2. Add per-stage timestamps.
3. Run at **lowest** and **highest** fixed CPU frequency.
4. Compare per-stage time ratios.

**Decision rule:**
- Decode/copy time barely changes while detection time ~doubles → **RQ2 is alive; proceed.**
- Everything scales cleanly as 1/f → shift main focus to RQ3 or RQ1.

---

## 8. Milestones (mapped to course assessment)

| Milestone | Weight | Deliverable from this project |
|---|---|---|
| Paper review | 10% | Review a paper that seeds related work (candidate: Pillai & Shin, SOSP 2001) |
| Proposal | 5% | Problem, RQs, hypotheses, system model (sections 2–3 of this file) |
| Mid-term review | 10% | Baseline pipeline + C_i(f) table + first energy numbers |
| Final demo | 20% | Live pipeline showing policies side by side, with energy and miss-ratio readouts |
| Final paper | 15% | 6-page IEEE paper: RQ2 main, RQ1/RQ3 supporting |

---

## 9. Threats to validity (draft)

- **Internal:** thermal throttling, background OS activity, and power-supply losses (if using the wall meter) could cause differences instead of the policy under test.
- **External:** one board, one Pi model, one detector; results may differ on chips with per-core DVFS or lower fixed power.
- **Construct:** whole-board power is not CPU power; energy per frame depends on how frames are counted (dropped vs. late).

---

## 10. Open questions

- [x] Image choice: Lite was tried but never joined the network; decision is the 64-bit **desktop image booted to console** (`multi-user.target`), non-essential services disabled, idle load measured and reported.
- [ ] Fix Pi Wi-Fi (Imager-written credentials not working on recent flashes).
- [x] Update bootloader EEPROM and record new version (done 2026-11-03).
- [x] Project repo created (scripts, setup runbook, results pushed after every session); see `README.md` and `docs/setup.md`.
- [ ] Freeze platform for the study: stop EEPROM auto-updates (`sudo apt-mark hold rpi-eeprom`) and avoid `apt upgrade` during the measurement phase (kernel/firmware changes would confound results).
- [ ] Find where hardware encode spends its ~12 ms CPU per frame (`perf record` on `hw_enc`); if it is frame copying, that is direct early evidence for H1.
- [ ] Fix the CPU frequency (`userspace` governor at a set step, or `performance`) for all measurement runs; CPU-seconds are not comparable across runs when `ondemand` changes the clock.
- [ ] Confirm with instructor that a Linux-based soft real-time project fits the scope.
- [ ] Confirm whether STM32F4 is acceptable (as a power logger now, or as a controller in a later extension).
- [ ] Decide the power-measurement upgrade (USB-C logger vs. INA226 + MCU).
- [ ] Choose the detector model.
- [ ] Choose the paper for the review talk.

---

## 11. Related work (seed list)

- Liu & Layland, J. ACM 20(1), 1973: RM/EDF and utilization bounds.
- Pillai & Shin, ACM SOSP 2001: real-time DVFS. **Key assumption under test.**
- Buttazzo, Real-Time Systems 29(1), 2005: RM vs. EDF comparison.
- Banakar et al., CODES 2002: scratchpad vs. cache (memory-boundedness context).
- Linux kernel docs: `SCHED_DEADLINE` and `schedutil`.

---

## 12. Results log

| Date | Experiment | Config | Result | Notes |
|---|---|---|---|---|
| 2026-11-03 | OS install | Raspberry Pi OS 2026-10-06, kernel 6.18.50, aarch64 | Boots; SSH works | Replaced previous install (Raspbian Bullseye 2021-10-30, 32-bit) |
| 2026-11-05 | Network access | Desktop image re-flashed; direct Ethernet link | SSH works at 10.42.0.41 | Wi-Fi not joining. PC's UFW blocked DHCP on the adapter, so the Pi's Ethernet came up then dropped; fixed with an interface-scoped allow rule |
| 2026-11-05 | Base setup | full-upgrade → kernel 6.18.60; console boot; ffmpeg 7.1.5 | Done | Ping passed but TCP was blocked until the UFW route rule was added (UFW forwards ICMP by default) |
| 2026-11-06 | Exp 00 codec check (run 2, `20261106T001525`) | 720p30 synthetic, 300 frames, `ondemand`, no power data | HW codec works (`/dev/video10` dec, `/dev/video11` enc). CPU-ms/frame: sw_enc 50, hw_enc 12 (net of pattern generation), sw_dec 10.8, hw_dec 0.5. Throughput: hw_enc 159 fps, sw_enc 66, hw_dec 184, sw_dec 315. 49–56 °C, no throttling | Run 1 agreed within ~2%. hw_enc still costs ~12 ms CPU/frame (≈ software decode), so not free; cause unknown (frame copies? driver polling? frequency effects under `ondemand`). Not paper data |

---

## Changelog

- **v0.8** (2026-11-06): Results log: experiment 00 run 2; open items on hardware-encode CPU cost and fixing the governor for measurements.
- **v0.7** (2026-11-05): Moved into the project repo as `docs/plan.md`; corrected stale Lite references in §4.3 note and §5; repo open item.
- **v0.6** (2026-11-05): Kernel 6.18.60 after upgrade; console boot target; HW codec devices; full list of PC-side network changes.
- **v0.5** (2026-11-05): Image decision (desktop, console boot); management link and UFW rule recorded; Wi-Fi open item.
- **v0.4** (2026-11-03): Recorded EEPROM update (2026-09-23); added platform-freeze task.
- **v0.3** (2026-11-03): Filled board, RAM, EEPROM, frequency steps, governors, ffmpeg; corrected frequency-step count in system model; added voltage-per-step measurement and EEPROM action.
- **v0.2** (2026-11-03): Added platform record (4.3), first results-log entry, open question on Lite vs. desktop image.
- **v0.1** (2026-11-02): Initial plan, RQs, hardware inventory and gaps, experimental design.
