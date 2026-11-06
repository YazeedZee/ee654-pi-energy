# EE654 Project: Energy vs. Deadlines in a Video Pipeline on Raspberry Pi 4 (v0.11)

**Course:** EE654 Embedded and Real-Time Systems, King Abdulaziz University (Fall 2026)
**Platform:** Raspberry Pi 4
**Status:** Setup / pre-baseline
**Working title:** *Offload or Throttle? Hardware Offloading, Energy and Deadline Predictability in a Passively Cooled Video Pipeline on the Raspberry Pi 4*

---

## 1. One-sentence summary

A video pipeline must finish every frame before a deadline (≈33 ms at 30 FPS). This project measures **how to meet that deadline with the least energy**, using three controls: *where* each stage runs (CPU, GPU, hardware codec), *how fast* the CPU runs (frequency scaling), and *how* stages are scheduled (Linux schedulers). It compares what scheduling and DVFS theory predicts against what the hardware actually does.

**Focus (decided 2026-11-06):** hardware offloading leads, under passive cooling where the firmware throttles the CPU; frequency scaling is supporting; scheduler comparison is optional.

**Contribution type:** measurement study testing an assumption of real-time analysis (fixed execution time) on a passively cooled platform.

---

## 2. Research questions

| ID | Question | Role in paper |
|---|---|---|
| **RQ1** | Does offloading video stages to the hardware codec reduce energy **and** keep frame deadlines met under passive cooling, and how much of the hardware–software gap is explained by thermal throttling? | **Main question** |
| RQ2 | How does per-stage execution time scale with CPU frequency (C(f) ∝ 1/f?), measured in short runs before the chip heats? | Supporting |
| RQ3 | Which Linux scheduler best protects frame deadlines under background load? | Optional (only if time allows) |

### RQ1: Offloading under passive cooling (main)
- **Configurations:** decode and encode on CPU (`libx264`, software decode) vs. hardware codec (`h264_v4l2m2m`); frame transfer by copy vs. zero-copy (dmabuf) if achievable.
- **Conditions:** short runs (cold chip, before throttling) vs. sustained runs (≥3 min, throttling allowed). Passive cooling by decision (see §4.1).
- **Hypothesis H1a (direct):** Hardware offload lowers energy per frame even without throttling, but less than its CPU savings suggest, because frame copies and fixed board power remain (exp 00: hardware encode still costs ~12 ms CPU per frame).
- **Hypothesis H1b (thermal):** In sustained runs, software paths heat the chip until the firmware lowers the clock; their per-frame time grows and deadline misses appear partway through the run. Hardware paths stay below the throttling point, so their timing stays flat.
- **Assumption under test:** real-time analysis (response-time analysis, utilization tests) treats a task's execution time C as fixed. Under passive cooling, C of CPU-heavy stages grows over the run as the clock drops; a task set that passes the analysis cold can miss deadlines minutes later.
- **Either outcome is a result:**
  - H1b holds → offloading buys timing predictability, not only energy; analysis must use the throttled clock, not the nominal one.
  - Pipeline load is too light to throttle → thermal effect not relevant at this workload; the paper reports the direct energy result (H1a) and the load level at which throttling begins.

### RQ2: Frequency scaling (supporting)
- **Measure:** per-stage execution time at fixed frequencies (600–1800 MHz), in short runs so the firmware does not override the setting.
- **Hypothesis H2:** CPU-bound stages (detection) scale as 1/f; memory-bound stages (decode, copies) scale less.
- **Use in the paper:** explains how much a throttling event (e.g., 1800 → 600 MHz) slows each stage, linking the RQ1 timing results to the clock trace.

### RQ3: Scheduling (optional)
- **Schedulers:** CFS (default), `SCHED_FIFO` with pinned cores, `SCHED_DEADLINE` (global EDF); background load from `stress-ng`.
- **Hypothesis H3:** similar averages; under load, CFS has a much worse latency tail.

---

## 3. System model (what the results assume)

- **Pipeline:** decode → preprocess → detect → overlay → encode.
- **Task model:** each stage is a task; frame period T = 33.3 ms (30 FPS); end-to-end deadline D = T (also test D < T if time allows).
- **Real-time class:** soft real-time. Claims are about deadline-miss ratio and latency tail, **not** guarantees.
- **Platform facts that shape the design:**
  - All four Cortex-A72 cores share **one clock**, so no per-core DVFS.
  - 13 frequency steps: 600–1800 MHz in 100 MHz increments. Core voltage is set by firmware, so not every step lowers voltage; voltage per step must be measured (`vcgencmd measure_volts core`).
  - Passive cooling (decision): sustained full load throttles the CPU (exp 01: 85.7 °C, clock down to 600 MHz). Temperature, ARM clock and throttle flags are logged in every run.
  - No on-board power telemetry on Pi 4; power is measured externally.
- **Input:** pre-recorded video files (repeatable), at least 2 resolutions × 2 motion levels.

---

## 4. Hardware

### 4.1 Available now
| Item | Use | Notes |
|---|---|---|
| Raspberry Pi 4 | Device under test | Check RAM size and board revision (`cat /proc/cpuinfo`) |
| Heatsinks (CPU, RAM) | Thermal control | Fine, but not enough alone under sustained load |
| Small fan (from kit) | — | Broken; not used. **Decision:** passive cooling (heatsinks, board placed in the PC's intake airflow). Throttling is treated as part of the system under test, measured per run and reported |
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
| Run length | short (cold chip, < 30 s), sustained (≥ 3 min, throttling allowed) |
| Frequency policy | performance, ondemand, schedutil, race-to-idle, slack controller, fixed frequencies |
| Scheduler | CFS, SCHED_FIFO pinned, SCHED_DEADLINE |
| Background load | none, stress-ng |

Not every combination will be run. RQ1 varies codec placement × run length with other factors at a reference setting; RQ2 varies fixed frequency in short runs; RQ3 (optional) varies scheduler and load.

### 6.2 Metrics
- **Energy per frame** (J), computed by integrating power over the run and dividing by frames. **Not** average watts alone.
- **Deadline-miss ratio** (% of frames with latency > D).
- **Frame latency:** median, p99, maximum. Not mean ± SD.
- **Per-stage execution time at each frequency** → C_i(f) table.
- CPU frequency over time, die temperature, throttle flags.
- Time to first throttle; fraction of run time throttled; per-stage execution time over the run (drift).

### 6.3 Statistics
- At least 10 runs × ~3 minutes per configuration, after warm-up.
- Report medians with confidence intervals; percentiles for latency.
- Use non-parametric tests (e.g., Mann–Whitney) where distributions are skewed.

### 6.4 Controls (one per likely reviewer question)
- [ ] Temperature, ARM clock and throttle flags logged every run; throttling reported per configuration
- [ ] Configurations interleaved (not blocked) so thermal history is balanced across conditions
- [ ] Same input files, same build, same compiler flags across configurations
- [ ] Warm-up period discarded
- [ ] HDMI, Wi-Fi, Bluetooth, USB devices in the same state every run (ideally disabled)
- [ ] Same power supply and cable throughout
- [ ] Frequency-switching latency measured and reported

### 6.5 Analysis-vs.-reality step
1. Measure each stage's execution time C_i in a short (cold) run, for hardware and software configurations.
2. Use response-time / utilization analysis with those cold C_i values to **predict** whether the pipeline meets its frame deadline.
3. Run sustained and **measure**: when do deadline misses begin, and do they coincide with clock drops in the trace?
4. Use the RQ2 C(f) table to check whether the measured slowdown matches the clock drop. Explain any remaining gap (memory-bound stages, copies).

---

## 7. Week-one feasibility test

**Goal:** confirm the main question has a measurable effect before building everything.

1. Build pipeline v1: decode → preprocess → detect → overlay → encode, with a timestamp at each stage boundary and a clock/temperature sample per frame.
2. Two modes: **software** (CPU decode + `libx264`) and **hardware** (`h264_v4l2m2m` decode + encode); same detector in both.
3. One sustained run (≥ 3 min) per mode, interleaved, `ondemand` governor, same input clip.
4. Plot per-frame stage times and the ARM clock over the run, for both modes.

**Decision rule:**
- Software mode throttles and its per-frame time grows while hardware mode stays flat → **H1b is alive; proceed.**
- Neither mode throttles at the real pipeline load → thermal angle is weak at this workload; lead with the direct energy result (H1a) and report the load at which throttling starts (exp 01 shows it does under full load).

---

## 8. Milestones (mapped to course assessment)

| Milestone | Weight | Deliverable from this project |
|---|---|---|
| Paper review | 10% | Review a paper that seeds related work (candidate: Pillai & Shin, SOSP 2001) |
| Proposal | 5% | Problem, RQs, hypotheses, system model (sections 2–3 of this file) |
| Mid-term review | 10% | Pipeline v1 in hardware and software modes, per-stage times with clock traces, first energy numbers |
| Final demo | 20% | Live pipeline in hardware and software modes side by side: frame times, clock, temperature, energy and deadline misses |
| Final paper | 15% | 6-page IEEE paper: RQ1 main (offloading under passive cooling), RQ2 supporting, RQ3 only if time allows |

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
- [x] Cooling decision: passive (heatsinks + PC intake airflow). Throttling is allowed, logged per run (temperature, ARM clock, `get_throttled`) and reported; HW and SW runs interleaved so both see the same thermal history. Discussed as a deployment-realistic condition in the paper.
- [ ] Fix the CPU frequency (`userspace` governor at a set step, or `performance`) for all measurement runs; CPU-seconds are not comparable across runs when `ondemand` changes the clock.
- [ ] Confirm with instructor that a Linux-based soft real-time project fits the scope.
- [ ] Confirm whether STM32F4 is acceptable (as a power logger now, or as a controller in a later extension).
- [ ] Decide the power-measurement upgrade (USB-C logger vs. INA226 + MCU).
- [ ] Choose the detector model.
- [ ] Choose the paper for the review talk.

---

## 11. Related work (seed list)

- Liu & Layland, J. ACM 20(1), 1973: RM/EDF and utilization bounds.
- Pillai & Shin, ACM SOSP 2001: real-time DVFS; source of the C(f) ∝ 1/f assumption tested in RQ2.
- Buttazzo, Real-Time Systems 29(1), 2005: RM vs. EDF comparison.
- Banakar et al., CODES 2002: scratchpad vs. cache (memory-boundedness context).
- Linux kernel docs: `SCHED_DEADLINE` and `schedutil`.
- *To find:* thermal-aware real-time scheduling and dynamic thermal management on embedded SoCs (for the H1b framing).

---

## 12. Results log

| Date | Experiment | Config | Result | Notes |
|---|---|---|---|---|
| 2026-11-03 | OS install | Raspberry Pi OS 2026-10-06, kernel 6.18.50, aarch64 | Boots; SSH works | Replaced previous install (Raspbian Bullseye 2021-10-30, 32-bit) |
| 2026-11-05 | Network access | Desktop image re-flashed; direct Ethernet link | SSH works at 10.42.0.41 | Wi-Fi not joining. PC's UFW blocked DHCP on the adapter, so the Pi's Ethernet came up then dropped; fixed with an interface-scoped allow rule |
| 2026-11-05 | Base setup | full-upgrade → kernel 6.18.60; console boot; ffmpeg 7.1.5 | Done | Ping passed but TCP was blocked until the UFW route rule was added (UFW forwards ICMP by default) |
| 2026-11-06 | Exp 00 codec check (run 2, `20261106T001525`) | 720p30 synthetic, 300 frames, `ondemand`, no power data | HW codec works (`/dev/video10` dec, `/dev/video11` enc). CPU-ms/frame: sw_enc 50, hw_enc 12 (net of pattern generation), sw_dec 10.8, hw_dec 0.5. Throughput: hw_enc 159 fps, sw_enc 66, hw_dec 184, sw_dec 315. 49–56 °C, no throttling | Run 1 agreed within ~2%. hw_enc still costs ~12 ms CPU/frame (≈ software decode), so not free; cause unknown (frame copies? driver polling? frequency effects under `ondemand`). Not paper data |
| 2026-11-06 | Exp 01 thermal soak (`data/raw/01_thermal_soak/`) | `stress-ng --cpu 4`, 600 s, `performance`, heatsinks only, **no fan** | Max 85.7 °C; clock fell to 600 MHz; `get_throttled` = `0xe0000` (freq capped, throttled, soft temp limit occurred; **no under-voltage**) | Under passive cooling, sustained full load makes the firmware lower the clock on its own. Led to the passive-cooling decision (§10) and the RQ1 thermal hypothesis (H1b). Power supply confirmed adequate |

---

## Changelog

- **v0.11** (2026-11-06): Research focus changed: RQ1 (offloading under passive cooling) is now the main question, testing the fixed-execution-time assumption; RQ2 supporting (short runs); RQ3 optional. Rewrote §2, §6.5, §7; updated title, system model, factors, metrics, milestones.
- **v0.10** (2026-11-06): Cooling decision: passive cooling, throttling measured and reported rather than prevented; controls updated.
- **v0.9** (2026-11-06): Fan broken; thermal soak shows throttling to 600 MHz at 85.7 °C with heatsinks only; cooling and thermal-protocol open items; controls updated.
- **v0.8** (2026-11-06): Results log: experiment 00 run 2; open items on hardware-encode CPU cost and fixing the governor for measurements.
- **v0.7** (2026-11-05): Moved into the project repo as `docs/plan.md`; corrected stale Lite references in §4.3 note and §5; repo open item.
- **v0.6** (2026-11-05): Kernel 6.18.60 after upgrade; console boot target; HW codec devices; full list of PC-side network changes.
- **v0.5** (2026-11-05): Image decision (desktop, console boot); management link and UFW rule recorded; Wi-Fi open item.
- **v0.4** (2026-11-03): Recorded EEPROM update (2026-09-23); added platform-freeze task.
- **v0.3** (2026-11-03): Filled board, RAM, EEPROM, frequency steps, governors, ffmpeg; corrected frequency-step count in system model; added voltage-per-step measurement and EEPROM action.
- **v0.2** (2026-11-03): Added platform record (4.3), first results-log entry, open question on Lite vs. desktop image.
- **v0.1** (2026-11-02): Initial plan, RQs, hardware inventory and gaps, experimental design.
