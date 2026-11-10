# EE654 Project: Energy vs. Deadlines in a Video Pipeline on Raspberry Pi 4 (v0.31)

**Course:** EE654 Embedded and Real-Time Systems, King Abdulaziz University (Fall 2026)
**Platform:** Raspberry Pi 4
**Status:** Setup / pre-baseline
**Working title:** *Offload or Throttle? Hardware Offloading, Energy and Deadline Predictability in a Video Pipeline on the Raspberry Pi 4*

---

## 1. One-sentence summary

A video pipeline must finish every frame before a deadline (≈33 ms at 30 FPS). This project measures **how to meet that deadline with the least energy**, using three controls: *where* each stage runs (CPU, GPU, hardware codec), *how fast* the CPU runs (frequency scaling), and *how* stages are scheduled (Linux schedulers). It compares what scheduling and DVFS theory predicts against what the hardware actually does.

**Focus (decided 2026-11-06; cooling updated 2026-11-07):** hardware offloading leads; cooling is a measured condition (fan on for reference runs, passive runs as the comparison); frequency scaling is supporting; scheduler comparison is optional.

**Contribution type:** measurement study testing an assumption of real-time analysis (fixed execution time) on a passively cooled platform.

---

## 2. Research questions

| ID | Question | Role in paper |
|---|---|---|
| **RQ1** | Does offloading video stages to the hardware codec reduce energy **and** keep frame deadlines met, and how does cooling (fan vs. passive) change the hardware–software gap in temperature and throttling? | **Main question** |
| RQ2 | How does per-stage execution time scale with CPU frequency (C(f) ∝ 1/f?), measured in short runs before the chip heats? | Supporting |
| RQ3 | Which Linux scheduler best protects frame deadlines under background load? | Optional (only if time allows) |

### RQ1: Offloading (main), cooling as a condition
- **Configurations:** decode and encode on CPU (`libx264`, software decode) vs. hardware codec (`h264_v4l2m2m`); frame transfer by copy vs. zero-copy (dmabuf) if achievable.
- **Conditions:** sustained runs (≥3 min). Fan on for reference runs (2026-11-07); passive runs (fan off) as the cooling comparison (see §4.1).
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
  - Cooling: fan always on for reference runs (2026-11-07). Without a fan, sustained full load throttles the CPU (exp 01: 85.7 °C, clock down to 600 MHz). Temperature, ARM clock and throttle flags are logged in every run.
  - No on-board power telemetry on Pi 4; power is measured externally.
- **Input:** pre-recorded video files (repeatable), at least 2 resolutions × 2 motion levels.

---

## 4. Hardware

### 4.1 Available now
| Item | Use | Notes |
|---|---|---|
| Raspberry Pi 4 | Device under test | Check RAM size and board revision (`cat /proc/cpuinfo`) |
| Heatsinks (CPU, RAM) | Thermal control | Fine, but not enough alone under sustained load |
| Small fan (from kit) | Active cooling | Broken until 2026-11-07 ~00:00, then working again. **Decision (2026-11-07): fan always on from here** (5 V, fixed speed); all reference runs use it. Earlier decision, superseded: passive cooling (heatsinks, board placed in the PC's intake airflow). Throttling is treated as part of the system under test, measured per run and reported |
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
| Power supply | Until 2026-11-06 ~23:00: **PC USB port** (likely cause of the under-voltage flag). From 2026-11-06 23:18: USB-C fast-charge brick and high-power cable; adequacy to be verified (`get_throttled` = 0x0 after a stress run) | `vcgencmd get_throttled` |
| Enclosure | Case on until 2026-11-06 ~23:00; **case removed** from then on (heatsinks, open board) | — |
| Management link | Direct Ethernet: PC USB-C adapter (`enp113s0u1c2`), NetworkManager "shared" mode, PC `10.42.0.1`, Pi `10.42.0.41`. PC firewall rules: `ufw allow in on enp113s0u1c2` and `ufw route allow in on enp113s0u1c2 out on enp6s0` (undo: `ufw delete allow in on enp113s0u1c2`; `ufw route delete allow in on enp113s0u1c2 out on enp6s0`). Docker `DOCKER-USER` rules: *record if added*. Pi apt forced to IPv4 (`/etc/apt/apt.conf.d/99force-ipv4`) | `nmcli connection show pi-link` |

**Note:** the full desktop image is used, booted to console (`multi-user.target`) with non-essential services disabled; Lite was tried and never joined the network. Idle load is to be measured and reported.

---

## 5. Software stack (planned)

- Raspberry Pi OS 64-bit, desktop image booted to console (headless), configured by `scripts/setup_pi.sh`
- ffmpeg with V4L2 M2M support (hardware codec)
- Detector: OpenCV 4.x DNN with MobileNet-SSD (Caffe, PASCAL VOC), fetched and checksum-verified by `scripts/fetch_model.sh`
- Pipeline v1: Python, PyAV (system ffmpeg, incl. `h264_v4l2m2m`) for decode/encode, `pipeline/run_pipeline.py`
- Inputs: Xiph `pedestrian_area` (low motion) and `crowd_run` (high motion), 720p30 and 1080p30, `scripts/fetch_inputs.sh`
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
| Detector load | detect every N frames, N ∈ {1, 3, 10} (load sweep: shows at what CPU load offloading starts to matter) |
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

## 6.6 Scheduling study (pipeline v2, RQ3 reframed)

Two periodic tasks on one core, rate-monotonic priorities: τ_frame (C_f, T = 1/fps, D = T) above τ_det (C_d, T = N/fps, D = T). Predictions from measured C (mean / p99 / max): U = C_f/T_f + C_d/T_d vs. the Liu & Layland bound 0.828 (sufficient test); exact RTA R_det = C_d + ⌈R/T_f⌉·C_f. Measured: frame miss ratio, detection response times and misses, skipped detection jobs. Comparison: CFS vs. SCHED_FIFO (RM) in sw and hw mode. Model caveats to discuss: hw frame task self-suspends while waiting for the video hardware; Python's GIL is a shared lock (blocking term B); C_max over a run is an observed maximum, not a guaranteed WCET.

---

## 7. Week-one feasibility test

**Goal:** confirm the main question has a measurable effect before building everything.

1. Build pipeline v1: decode → preprocess → detect → overlay → encode, with a timestamp at each stage boundary and a clock/temperature sample per frame. **Done:** `pipeline/run_pipeline.py`, run by `experiments/02_week1_offload.sh` (default N = 3).
2. Two modes: **software** (CPU decode + `libx264`) and **hardware** (`h264_v4l2m2m` decode + encode); same detector in both.
3. One sustained run (≥ 3 min) per mode, interleaved, `ondemand` governor, same input clip.
4. Plot per-frame stage times and the ARM clock over the run, for both modes.

**Outcome (2026-11-07, reference runs):** hw sustains 30 fps (utilization 0.86) where sw cannot (1.66); at equal work hw uses 52% less CPU and runs 7.3 °C cooler. No throttling at the pipeline's load, with or without fan, within 3 min → per the rule below, lead with the direct result (H1a) and report the throttling threshold (exp 01: full 4-core load, no fan) and the thermal headroom.

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
| Final paper | 15% | 6-page IEEE paper: RQ1 main (offloading; cooling as a condition), RQ2 supporting, RQ3 only if time allows |

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
- [x] Cooling decision (superseded 2026-11-07 by fan always on): passive (heatsinks + PC intake airflow). Throttling is allowed, logged per run (temperature, ARM clock, `get_throttled`) and reported; HW and SW runs interleaved so both see the same thermal history. Discussed as a deployment-realistic condition in the paper.
- [ ] Fix the CPU frequency (`userspace` governor at a set step, or `performance`) for all measurement runs; CPU-seconds are not comparable across runs when `ondemand` changes the clock.
- [x] Reference runs on the verified supply (2026-11-06/07): 30 fps clean; 15 fps clean for CPU, temperature invalid (airflow changed).
- [x] Reference runs with fan on (2026-11-07): 30 fps `20261107T001714`, 15 fps `20261107T003226`; both clean.
- [x] Interim energy result with the wall meter (2026-11-07, `20261107T130959/wall_power.txt`): hw ≈ −1.0 W, −16% J/frame total, −37% above idle.
- [x] Power-meter decision (2026-11-07): **no logging meter will be bought**; energy evidence = AC wall meter read by eye, reported as approximate (direction robust, magnitude ±0.2–0.3 W per reading). Optional zero-cost improvement: film the meter display during runs and transcribe readings at fixed intervals for means and confidence intervals.
- [x] Governor test (2026-11-07, `20261107T134531`): no measurable power difference; performance removes clock dips and all >145 ms hw detection frames (causal).
- [ ] Detector load sweep N ∈ {1, 3, 10} at 15 fps (fan on).
- [x] Pipeline v2 built (2026-11-07): `pipeline/run_pipeline_v2.py`, experiment `04_rms.sh`. Two periodic tasks on **one core** (core 3, single-threaded codecs and OpenCV) so uniprocessor theory applies: frame task (T = 1/fps) above detect task (T = N/fps) by rate-monotonic order. CFS vs. SCHED_FIFO RM priorities; C measured per job from thread CPU time; Liu & Layland test and RTA computed per run and compared with measured responses/misses. Frame-path colour conversion uses libswscale on a bulk copy (keeps the frame task out of OpenCV's shared thread pool).
- [x] Experiment 04 (2026-11-10, `20261110T202628`): hw schedulable and analysis holds; sw unschedulable on one core; RM vs SCHED_OTHER identical when schedulable, opposite failure modes under overload.
- [x] Experiment 04 with background load (2026-11-10, `20261110T204647`): RM unaffected; SCHED_OTHER 100% frame misses, 40% detection jobs lost. Scheduling section complete.
- [ ] **Write the paper** (IEEE format, LaTeX, `paper/`): lead findings = frame-access trap (exp 03), governor causes tail with no energy return, offloading decides schedulability on one core, RM needed to make the analysis hold under co-running load.
- [ ] Before making the repo public: license, README clean-up, commit-email decision.
- [ ] LinkedIn post (after the paper).
- [ ] Terminology: label the default policy SCHED_OTHER (EEVDF on kernel 6.18), not CFS, in the paper.
- [ ] Cooling comparison: the clean passive 30 fps run (`20261106T233239`) serves as the **no-fan** condition against the fan-on reference; blower comparison still later.
- [ ] Note in each run's record: board position and whether the PC was in use.
- [ ] Cooling bracket: repeat exp 01 (5 min) with case off, then with an electric air blower at fixed position/speed; compare with the case-on run (85.7 °C, throttled to 600 MHz).
- [ ] Confirm with instructor that a Linux-based soft real-time project fits the scope.
- [ ] Confirm whether STM32F4 is acceptable (as a power logger now, or as a controller in a later extension).
- [ ] Decide the power-measurement upgrade (USB-C logger vs. INA226 + MCU).
- [x] Detector and inputs chosen (2026-11-06): conventional choices fixed before any results (MobileNet-SSD; Xiph clips). Detector load is swept (N) rather than picked, so the result does not depend on one hand-chosen workload.
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
| 2026-11-06 | Exp 02 smoke test (`20261106T204009`) | pipeline v1, pedestrian_area 720p30, N = 3, 20 s × (sw hw hw sw) | **Both modes overloaded:** sw 11.1 fps, hw 5.0 fps (target 30). Detection ≈ 115 ms per call. **hw slower and uses more CPU per frame** (302 vs 239 ms) although its decode (0.4 ms) and encode (1.7 ms) stages are tiny: ~150 ms per frame unaccounted for in the printed stages | Suspect: CPU access to hardware-codec buffers (colour conversion of decoded frames), same family as exp 00's 12 ms hw-encode cost → early H1 evidence, to confirm. Runner fixed: runs bounded by wall-clock time; service time and utilization reported, since latency is meaningless when overloaded |
| 2026-11-06 | Exp 02 smoke test 2 (`20261106T211822`) | as above, new runner | hw `to_bgr` 142–162 ms per frame vs sw 4–5 ms. sw cannot reach 30 fps even on frames without detection (~48 ms typical service time). Detection 110–155 ms per call | Locates the hw slowdown in the colour conversion of decoded frames. Exp 00's "hw decode nearly free" held only because its null output never read the pixels |
| 2026-11-06 | Exp 03 frame access (`20261106T215616`) | 720p, 150 frames, medians | Raw copy of decoded planes: sw 0.93 ms (1483 MB/s), **hw 2.33 ms (595 MB/s)**. Copy then OpenCV convert: hw 2.33 + 2.03 ms. **PyAV direct conversion of hw frames: 138 ms** (sw 3.9 ms) | Hardware decoder buffers are ~2.5× slower for the CPU to read (small, real data-movement cost: H1). The 138 ms is the conversion's access pattern on that memory, not the memory alone: copy-then-convert is ~30× faster. Pipeline now uses copy-then-convert for both modes (`--convert copy`, default); direct path kept as an option |
| 2026-11-06 | Exp 02 smoke test 3 (`20261106T215838`) | copy-then-convert, **N = 10**, 20 s × (sw hw hw sw) | **hw ≈ 30 fps, utilization 0.87–0.97; sw 17.5 fps, utilization 1.66.** CPU per frame hw 75–83 ms vs sw 136 ms. hw to_bgr 10 ms in the pipeline (4.4 ms in isolation, exp 03). Miss ratio hw 72–93% despite utilization < 1. 41–55 °C, short runs | First configuration where hw is feasible and sw is not; the conversion fix reversed the hw/sw ordering. Thin hw margin: a clock drop could push it past 1 (test in sustained run). High miss ratio at utilization < 1 = queueing after each ~125 ms inline-detection frame; utilization and throughput are the reliable metrics for pipeline v1; a meaningful miss ratio needs detection decoupled (pipeline v2) |
| 2026-11-06 | **Exp 02 week-one run** (`20261106T220413`) | N = 10, 30 fps, 180 s × (sw hw hw sw), 60 s gaps | **hw 30.0 fps, utilization 0.88–0.89; sw 17.6–17.8 fps, utilization 1.66–1.69.** CPU per frame hw 76 ms vs sw 136–138 ms (−45%). Cores used hw 2.28 vs sw 2.42. Temperature 41–47 → 57–60 °C, still rising at the end; no throttling expected at these temperatures (check clock.csv) | **H1a supported** (hw feasible, sw not; repeatable to ±2%). **H1b not triggered** in 3 min. Key observation: at equal *frame rate* hw does 70% more work, so total CPU (and heat) is about the same as sw; offload savings went into throughput, not cooling. Next: equal-work comparison (both at 15 fps, which sw sustains) and a longer run to see where temperature settles |
| 2026-11-06 | Clock check of week-one run | `clock.csv` of `20261106T220413` | Sticky throttle flags **`0x50000`**: under-voltage has occurred (bit 16) and throttling has occurred (bit 18) since boot, with max temperature only 60.8 °C. Min clock 600 MHz, but the log includes idle gaps where the governor lowers the clock on purpose | **Under-voltage seen for the first time** (exp 01 showed none); throttling here was voltage-caused, not thermal. Timing unknown from sticky bits: per-run check with `analysis/clock_check.py` (bits 0–3, 'active now') pending. Corrects the earlier 'power supply adequate' note |
| 2026-11-06 | **Exp 02 equal-work run** (`20261106T222312`) | **15 fps**, N = 10 (1.5 detections/s both modes), 180 s × (sw hw hw sw) | **sw: 2.21–2.24 cores, 147–149 ms CPU/frame, utilization 0.88–0.90, 42–44 → 58 °C. hw: 1.07 cores, 71 ms CPU/frame, utilization 0.41–0.42, 44–46 → 49–50 °C.** Miss ratio sw 58–62%, hw 21% | At identical work, **hw uses 52% less CPU and ends ~9 °C cooler** after 3 min: the thermal-headroom form of H1b. Repeatable within ~2%. Energy not yet measured (needs power meter) |
| 2026-11-06 | **Configuration change** | — | Power: PC USB port → USB-C brick. Case removed | All exp 00–02 runs so far: case on, PC USB power. Runs from here on are not directly comparable with them. Pending: verify brick (stress + `get_throttled`), run `clock_check.py` on the two long exp 02 runs |
| 2026-11-06 | `clock_check.py` on both long exp 02 runs | per-run windows, bits 0–3 | Under-voltage + throttling active in ~6 samples per run (≈3 s at 600 MHz of 180 s, ~2%), 12 in one equal-work sw run, none in one week-one sw run. Median clock 1800 MHz in every run. Both modes affected about equally | Throttling was supply-caused (PC USB) and brief; too small and too even across modes to explain the 45–52% differences, so conclusions stand. Runs classed **preliminary**. Reference dataset: repeat both on the new supply with the case off |
| 2026-11-06 | **Reference run, 30 fps** (`20261106T233239`) | USB-C brick, case off, N = 10, 180 s × (sw hw hw sw) | sw 17.6 fps, utilization 1.68, 136.7–137.6 ms CPU/frame; hw 30.0 fps, utilization 0.88–0.89, 75.2–76.7 ms CPU/frame. Clock 1800 MHz throughout, no throttle bits, sticky flags 0x0. 56–58 → 68–72 °C | **Reference dataset.** Matches the preliminary run within 1–2%: the earlier under-voltage effect was negligible. Supply verified adequate |
| 2026-11-07 | **Reference run, 15 fps equal work** (`20261106T234758`) | as above, FPS = 15 | sw 2.17–2.21 cores, 144–148 ms CPU/frame, utilization 0.86–0.88; hw 1.04–1.05 cores, 70 ms CPU/frame, utilization 0.40–0.41. No throttle bits. hw clock min 800 MHz (governor, light load). **Temperatures inconsistent:** run 1 sw ended 62 °C but run 2 started 42 °C; hw runs cooled while running (42 → 39 °C); run 4 started 34.6 °C | **CPU result replicated: hw −52% CPU at equal work.** Temperature comparison **not valid** for this run: cooling changed during the experiment. **Cause (2026-11-07): the Pi's own fan started working again partway through** (PC intake airflow may also vary with PC load). The ~9 °C difference from the preliminary run remains unconfirmed. Thermal comparisons need stable surroundings; ambient/airflow to be recorded |
| 2026-11-07 | **Exp 02 reference, fan on, 30 fps** (`20261107T001714`) | fan always on, case off, USB-C brick, PC idle, N = 10, 180 s × (sw hw hw sw) | **sw utilization 1.66, 135 ms CPU/frame, 17.8–17.9 fps; hw utilization 0.86, 73.5 ms CPU/frame, 30.0 fps.** 32–35 → 44–45 °C. Clock 1800 MHz throughout, no throttle conditions, flags 0x0 | **Reference dataset (30 fps).** Versus the no-fan run (`20261106T233239`, 68–72 °C): fan lowers end temperature ~25 °C but changes utilization only ~2%: at this load cooling sets temperature, not speed |
| 2026-11-07 | **Exp 02 reference, fan on, 15 fps equal work** (`20261107T003226`) | as above, FPS = 15 | **sw 2.17–2.18 cores, 145 ms CPU/frame, utilization 0.87; hw 1.04–1.06 cores, 70 ms CPU/frame, utilization 0.41.** Matched pair from 34.1 °C: **hw → 37.0 °C, sw → 44.3 °C** (+2.9 vs +10.2 °C). hw clock dips to 800 MHz (governor, light load); no throttle conditions, flags 0x0 | **Reference dataset (15 fps).** Equal work: hw −52% CPU and **7.3 °C cooler** after 3 min. Thermal-headroom result confirmed in clean conditions |
| 2026-11-07 | **Analysis fix** (`plot_02.py`, `clock_check.py`) | — | Both used each frame's *scheduled* release time as the time axis / check window. For overloaded runs (sw at 30 fps: ~3200 frames in 180 s) that ended at ~107 s, so the last ~40% of those runs was missing from plots and clock checks. Fixed: time = completion (release + latency); rolling means over fixed time windows; warm-up excluded from the stage panel | Re-checked fan-on 30 fps reference: sw runs now 340 samples, still no throttle conditions. Reference conclusions unchanged (sticky flags were 0x0 anyway). Preliminary runs' sw clock checks were partial (already marked preliminary). Earlier note that sw had fewer samples 'because the sampler slowed' was wrong: it was this window bug |
| 2026-11-07 | **Governor dips vs frame time** (`20261107T003226`, hw runs) | 15 fps, `ondemand`; frames within ±0.3 s of a clock sample < 1800 MHz | ~21 clock dips (800–1000 MHz) per hw run, none in sw runs. Near a dip, hw detection frames median **140–159 ms vs 121–122 ms** normally; other frames 18.0 vs 14.9 ms (+16–30%) | The light load that offloading creates lets `ondemand` lower the clock, and frames that start during a dip run slower: an energy-saving vs. timing-outlier trade-off (links RQ1 and RQ2). Association at ~0.5 s sampling, not yet causal: test hw at 15 fps under `performance` vs `ondemand` |
| 2026-11-07 | **First energy result: wall meter, equal work** (`20261107T130959`, readings in `wall_power.txt`) | 15 fps, N = 10, 120 s × (sw hw hw sw), fan on; AC wall meter read by eye | **Idle 3.6 W. sw ≈ 6.3 W (runs 6.2–6.5, 6.1–6.4); hw ≈ 5.3 W (4.7–5.6, 5.4–5.6).** Both sw runs above both hw runs. Per frame: sw ≈ 0.42 J total / 0.18 J above idle; hw ≈ 0.35 J / 0.11 J | **H1a supported with first energy numbers:** CPU −52%, but power added above idle only ≈ −37%, and total energy per frame only ≈ −16% because the 3.6 W idle floor is paid in both modes. Wider hw spread consistent with governor clock dips. Limits: manual AC-side readings (charger losses + fan included), ≈ ±0.2–0.3 W; direction robust, magnitude to confirm with a logging meter |
| 2026-11-07 | **Governor test** (`20261107T134531`, readings in `wall_power.txt`) | hw only, 15 fps, N = 10, 120 s × (ondemand, performance, performance, ondemand); wall meter read every ~5 s (22–31 readings/run) | **Power: ondemand 5.50 / 5.09 W, performance 5.12 / 5.38 W; pooled 5.26 vs 5.26 W** (Mann-Whitney p = 0.41). performance: clock min 1800 MHz, p99 service 133.9–134.3 ms, 68.6–68.8 ms CPU/frame. ondemand: clock min 700–800 MHz, p99 136.3–138.6 ms; run 4 slower overall (median 17.9 vs 15.1 ms, 75.8 ms CPU/frame) | **ondemand gives no measurable energy saving at this load** (difference ≪ ~0.4 W run-to-run spread) but adds timing variability → supports H2b (with high fixed board power, running fast costs about the same). performance removes the dips; p99 improves only ~2–4 ms, so the dips explain only part of the tail (count of >145 ms frames pending). Meter readings alias with 1.5 Hz detection bursts: use means of many readings. sw−hw 1.0 W difference remains above the ~0.4 W run-to-run spread |
| 2026-11-07 | **Governor test: tall-frame count** (`20261107T134531`) | detection frames after warm-up, 178 per run | **performance: 0 detection frames > 145 ms (max 142.8 / 144.1 ms).** ondemand: 9 frames > 145 ms and 4 > 160 ms (max 174.6 ms) in run 1; 1 > 145 ms (max 147.2 ms) in run 4. Median detection-frame time equal (121.4–121.6 ms; run 4 125.2). Time at lowered clock: ondemand 7% and 33%, performance 0% | **Causal (controlled manipulation): the tall hw frames are caused by ondemand's clock dips.** Fixing the clock removes the tail without changing typical frame time. ondemand behaviour also varies run to run (7% vs 33% low-clock time). Run 4's lowest power (5.09 W) hints at a small saving but is within run-to-run spread |
| 2026-11-10 | **Exp 04: two-task RM on one core** (`20261110T202628`, smoke test `20261107T211058`) | pipeline v2, core 3, 15 fps, N = 10, 90 s × (hw:rms hw:cfs sw:cfs sw:rms sw:rms sw:cfs hw:cfs hw:rms) | **hw:** C_frame 18.7–19.2 ms mean / 24 ms max, C_det ≈ 303 ms; U(max C) 0.82 (≤ 0.828, LL passes); RTA predicts R_det ≤ 498–501 ms, measured max 445–448 ms; 0% frame misses, 131/131 detection jobs, **identical under rms and SCHED_OTHER**. **sw:** C_frame 93–95 ms mean > 66.7 ms period (U_frame ≈ 1.8, unschedulable); **rms** 10.7 fps, detection starved (1/92 completed, 90–91 skipped); **SCHED_OTHER** 7.9 fps, all 67 detection jobs completed, responses up to 43 s | On one core, **offloading decides schedulability**: hw passes LL and RTA, sw cannot meet the frame period at all. RTA held (≈11% pessimistic). **Prediction wrong:** SCHED_OTHER gave no frame misses for schedulable hw; the frame task sleeps most of the time and the default scheduler (EEVDF on kernel 6.18, not CFS) serves it promptly on wake-up, mimicking RM. Under overload the policies fail oppositely: RM protects the high-rate task and starves detection; SCHED_OTHER shares and degrades both. Next: background CPU load on the same core, where RM and SCHED_OTHER should differ when schedulable |
| 2026-11-10 | **Exp 04 with background load** (`20261110T204647`) | hw only, BG = 2 stress-ng CPU workers pinned to core 3 (SCHED_OTHER), 90 s × (rms cfs cfs rms) | **RM: 15.0 fps, 0% frame misses, 131/131 detection jobs, R_det max 445–447 ms ≤ RTA 497–498 ms: unchanged from no load.** **SCHED_OTHER: 13.6–13.8 fps, 100% frame misses (throughput below release rate → backlog), 70–71/118–120 detection jobs completed, 48–49 skipped, R_det up to 8.9–10 s** | **Prediction confirmed.** Analysis said "schedulable" for both, but only RM made it true: RM keeps lower-priority work out of the analysed task set, so the analysis stays valid; SCHED_OTHER gives the frame task only a fair share (~1/4 of the core), so the analysis is meaningless under it. Identical behaviour without background load hides this difference |

---

## Changelog

- **v0.31** (2026-11-10): Exp 04 background-load result (RM protects the analysed task set; SCHED_OTHER fails); experiments complete; writing items.
- **v0.30** (2026-11-10): Exp 04 results (offloading decides schedulability on one core; RTA holds; RM ≈ SCHED_OTHER when schedulable, opposite failures under overload); background-load option; EEVDF terminology.
- **v0.29** (2026-11-07): Pipeline v2 (two-task RM on one core) and experiment 04; §6.6 scheduling study.
- **v0.28** (2026-11-07): Governor tall-frame count: performance eliminates the >145 ms hw frames (causal link to ondemand dips).
- **v0.27** (2026-11-07): Governor test result (ondemand ≈ performance in power; performance removes dips); meter aliasing note.
- **v0.26** (2026-11-07): Decision: no logging power meter; wall-meter evidence framed as approximate. Exp 02 script: per-run mode/governor list (RUNS) for the governor test.
- **v0.25** (2026-11-07): First energy result (wall meter, equal work): hw −1.0 W, −16% J/frame total, −37% above idle vs. −52% CPU.
- **v0.24** (2026-11-07): Analysis-script fix (time axis / check window for overloaded runs); governor-dip vs frame-time finding; governor test open item.
- **v0.23** (2026-11-07): Fan-on reference runs logged (30 and 15 fps, clean); week-one outcome recorded in §7; next items: energy measurement, load sweep, pipeline v2.
- **v0.22** (2026-11-07): Title, focus and RQ1 reworded for fan-on reference runs (cooling now a condition, not the premise). Cooling decision changed: fan always on for reference runs; passive 30 fps run kept as the no-fan condition; reference re-runs (30 and 15 fps) with fan on as open items.
- **v0.21** (2026-11-07): 15 fps temperature confound attributed to the Pi fan restarting; fan unplugged for reference runs; fan-on condition added as later item.
- **v0.20** (2026-11-07): Reference runs (30 fps and 15 fps) logged: CPU results replicated and clean; 15 fps temperatures invalid (airflow changed); open items for stable-surroundings repeat.
- **v0.19** (2026-11-06): Clock check of long runs (~2% under-voltage throttling, both modes); runs marked preliminary; re-run open item.
- **v0.18** (2026-11-06): Power source and enclosure recorded (PC USB → USB-C brick; case removed); configuration-change entry; cooling-bracket open item.
- **v0.17** (2026-11-06): Results log: equal-work run (hw −52% CPU, ~9 °C cooler); under-voltage flag found; `analysis/clock_check.py`.
- **v0.16** (2026-11-06): Results log: week-one run (H1a supported, H1b not triggered in 3 min; equal-work comparison next). Exp 02 script takes FPS.
- **v0.15** (2026-11-06): Results log: exp 02 smoke test 3 (N = 10: hw feasible, sw overloaded).
- **v0.14** (2026-11-06): Results log: exp 02 smoke test 2 and exp 03 (hardware frame access); pipeline conversion fix.
- **v0.13** (2026-11-06): Results log: exp 02 smoke test (both modes overloaded; hw unexpectedly slower).
- **v0.12** (2026-11-06): Detector, inputs and pipeline v1 recorded; detector load sweep (N) added as a factor.
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
