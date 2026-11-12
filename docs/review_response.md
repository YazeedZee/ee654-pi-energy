# Response to the external review of paper draft v1 (plan v0.32)

2026-11-10. Audit of the reviewer's handoff against the code (`pipeline/`, `experiments/`, `analysis/`), the raw logs (`data/raw/`) and `paper/main.tex`. Every number below comes from existing logs. To recompute them, run `python3 analysis/review_audit.py`; the output is saved in `docs/review_audit_numbers.txt`.

**Status, 2026-11-11.** Decision: no further experiments; the paper presents what was measured. Draft v2 (`paper/main.tex`) applies all of category A and B below. The new measurements in category C and the extensions in D are not run; the paper's Limitations section states what they would have addressed. The meter is a MECHEER plug-in energy meter (0.1 W display steps; its manual states no accuracy and a 0.5 W minimum load).

Verdicts: **Confirmed** (the evidence supports the concern), **Partly valid** (the concern is right in part, or the logs already answer part of it), **Unsupported** (the code or data contradicts it), **N/A**.

## 1. Verdicts, point by point

### 1. Related work and novelty: Confirmed, but one source is mis-characterised

| Source | Status | What it supports |
|---|---|---|
| Khernache et al., J. Syst. Archit. 2021 (HEVC hw vs sw decoding energy) | Exists ([HAL](https://hal.telecom-paris.fr/LAB-STICC_SHARP/hal-03127340v1), [X-MOL](https://www.x-mol.com/paper/1348380691536961536)). Full text not read. | Precedent for "whole-system saving < decoder-level saving". Cite it. Do not present that idea as ours. |
| VideoCoreCluster, Liu et al. ([USENIX ATC'16](https://www.usenix.org/conference/atc16/technical-sessions/presentation/liu); [journal](https://wings.cs.wisc.edu/publications/videocorecluster-energy-efficient-low-cost-and-hardware-assisted-video-transcoding-system/)) | Exists. Full text not read. | Pi hardware transcoding energy, CPU↔VPU transfer cost. Cite. |
| Marasini & Zhou 2026, [arXiv 2609.04705](https://arxiv.org/pdf/2609.04705) | **Read.** Pi 5, passive cooling, YOLOv8n. A fixed full clock reached 84.8 °C with 1823 throttle events in 30 min. Their temperature-aware frequency *cap* removed throttling at about 4% FPS cost and about 9% less energy per frame. | This is a direct **counterpoint** to our "fix the clock" advice: with weaker cooling, fixing the clock at maximum is what causes throttling. Cite it in §VI and narrow our recommendation (see 9). |
| [Picamera2 issue #740](https://github.com/raspberrypi/picamera2/issues/740) | **Read** (rendered page, summarised by a fetch tool). It concerns camera dma-buf buffers, not the V4L2 M2M decoder. The maintainer measured slow *memcpy* (about 40 ms per 18 MB on a Pi 4, ≈450 MB/s), said the buffers are known to be "slow", and pointed out that one can work on the uncopied buffers. On the rendered page no maintainer mentions cached or uncached mappings, and no one recommends copying first. A user asked about dma-buf SYNC_START/END and got no answer. | It supports **our raw-copy observation** (595 MB/s from hardware-decoder buffers against 1483 MB/s). It does **not** support the review's claim that a maintainer "explicitly recommends copying into cached memory before processing". Cite it as precedent for slow CPU access to Pi DMA buffers only. |
| [Pi forum t=310267](https://forums.raspberrypi.com/viewtopic.php?t=310267) | **Not verified.** The fetch was blocked and searches did not surface it. | Do not cite it until we have read it. If you can open it, paste the relevant posts. |
| Bocan et al. 2026, [Electronics 15(5):967](https://www.mdpi.com/2079-9292/15/5/967) | The URL is indexed, but the content was blocked by a bot check, so title and contents are not verified. | Cite only after reading it. |
| Loudaros et al. 2025, DOI 10.1145/3721889.3721925 | **Not found.** Neither the DOI nor the title turned up in search. | Do not cite until verified. It may exist, but we have not seen it. |
| [RPi H.264 encoder white paper](https://pip-assets.raspberrypi.com/categories/685-app-notes-guides-whitepapers/documents/RP-010033-WP-1-H.264%20encoding%20performance%20on%20Raspberry%20Pi%205_series%20computers.pdf) | Not fetched. | Useful method reference for bitrate and quality checks. |

Required changes: add a Related Work section. Contribution bullet 2 ("identification of a data-access trap… factor of 30") overclaims on two counts: the slow-buffer phenomenon is documented, and our factor of 30 mixes two converters (see 6). Reframe it as *quantifying the cost on the decoder path, with a same-converter comparison*.

### 2. Throughput versus deadline compliance: Confirmed, and worse than the review says

- v1 at 30 fps: hardware sustains 30.0 fps, yet its miss ratio is 70.8–71.4% with the fan and 73–75% passive. Software misses 100%.
- **v1 at 15 fps (the "equal work" condition) also misses deadlines**: software 51.6–54.2%, hardware 20.2–20.6% (all four sessions). Inline detection makes every detection frame (one in ten) and the frame after it late. The draft never says this. Its claim that "both modes sustain" 15 fps is true for throughput only.
- v2 on one core: RM had 0 frame misses in 4 × 1306 frames, with and without background load. The default policy with background load missed 100%.
- Text to fix:
  - §IV heading "Real time at 30 frames/s".
  - "utilization, not the miss ratio, is the meaningful measure".
  - Conclusion "made this pipeline real-time".
  - Intro "We built a real-time pipeline".
  - Abstract "sustain 30 frames/s" without its miss ratio.
- Add the detection cadence everywhere a frame rate appears: 3 detections/s at 30 fps, 1.5/s at 15 fps.

### 3. Interpretation of the scheduling analysis: Confirmed

- **Retrospective**: `run_pipeline_v2.py` lines 271–287 compute the Liu–Layland test and RTA from `c_f.max()` and `c_d.max()` of the *same run* whose responses they are compared with. This is a consistency check, not a prediction.
- "Only RM makes the analysis true" is a category error. Fixed-priority RTA says nothing about `SCHED_OTHER`. The default policy is an empirical baseline. The same error appears in the abstract ("RTA bounds the measured behaviour only when RM…") and in the conclusion.
- **Harmonic periods** (T_d = 10 T_f): under the ideal assumptions RM schedules any harmonic set with U ≤ 1. "Just inside the two-task bound of 0.828" therefore suggests a margin of 1% when the analytical slack is 18%.
- **C_d max is missing** from Table II. From the logs:

  | Condition | C_d max |
  |---|---|
  | hw RM | 304–305 ms |
  | hw default | 307–310 ms |
  | sw RM | 293–295 ms |
  | sw default | 298–299 ms |
  | hw RM + bg | 304–305 ms |
  | hw default + bg | 317–321 ms |

- Inputs to reproduce RTA (run1_hw-rms): C_f = 24.421, C_d = 305.345, T_f = 66.667 ms. The iteration R = C_d + ⌈R/T_f⌉·C_f goes 329.8 → 427.4 → 476.3 → 500.7 → 500.7 ms. Put this in the paper.
- Missed by the review: measured detection response is timed from the *nominal* frame release. The job reaches the mailbox 13.8–14.1 ms later (median; max 16 ms), so measured R includes a release jitter that RTA does not model. The bound still held, but say so.
- "Observed maxima are not WCETs" appears only in Limitations. It must also appear in the abstract, in §VII and in the conclusion.

### 4. Task model and job accounting: Confirmed, and the logs settle every question asked

The code, by line in `run_pipeline_v2.py`:

| Question | Answer |
|---|---|
| Wall-clock or frame-driven releases? | **Frames** are released on the wall clock (`release = t0 + i·T`, line 221). **Detection jobs** are handed over when frame *i* with `i % N == 0` is *processed* (lines 230–232). The job's release time is set to that frame's nominal release (line 232), so response is measured from the nominal time. |
| Can backlog delay or bunch submissions? | It **delays and thins** them; it does not bunch them. Under backlog, frames run back to back, so hand-offs come every N processed frames (rate = processed fps / N). Median lag from nominal release to hand-off: sw default 22.5–22.8 s, sw RM 13.7 s, hw default + bg 3.8–4.5 s, hw RM 14 ms. |
| Occupied mailbox slot? | The previous, never-started job is overwritten and counted as `skipped` (lines 119–124). |
| Drained after the run? | Yes. `mailbox.close()` lets the detector take a pending job, then `join(timeout=5)`. Jobs that finish after the timed run are counted as completed, with their true response. A job still running 5 s after stop would be lost silently. This never happened; "unfinished" is 0 in every run. |
| Bug found | `jobs_released = len(range(warm_f, len(rows), N))` counts indices ≡ 5 mod 10, not the frames actually handed over. It is off by one in run5_sw-rms (logged 92, actual 91). Fix it in the code. |

Corrected accounting (warm-up excluded; deadline 666.7 ms; the nominal count is 131 in every run):

| Condition (2 runs each) | Submitted | Overwritten | Completed (after run) | On time | R max |
|---|---|---|---|---|---|
| hw RM | 131 | 0 | 131 (1) | 131 | 445–447 ms |
| hw default | 131 | 0 | 131 (1) | 131 | 445–448 ms |
| sw RM | 91–92 | 90–91 | 1 (1) | **0** | 26–27 s |
| sw default | 67 | 0 | 67 (0–1) | **0** | 42.5–42.9 s |
| hw RM + bg | 131 | 0 | 131 (1) | 131 | 445–447 ms |
| hw default + bg | 118–120 | 48–49 | 70–71 (1–2) | **0** | 8.9–10.0 s |

What this changes in the draft:

- "1/92" was a job completed **after** the run. Under RM in software mode the detector never ran during the run: it was notified but never scheduled, because the FIFO-80 frame task never slept.
- "67/67" is 67 of 131 nominal releases, none of them on time. Of the 42.9 s worst response, 42.4 s is frame-backlog lag before hand-off; the detector itself was not the bottleneck.
- "40% of detection jobs were lost" (48/118 submitted) should read: 46–47% of nominal jobs never completed, and 100% were late.
- **Staleness of the boxes drawn on output frames**, measured in video time between the analysed frame and the shown frame:
  - hw RM: median 11 frames (733 ms), max 16–17 (1.07–1.13 s).
  - hw default + bg: median 31 frames (2.1 s), max 44 (2.9 s).
  - sw RM: no boxes at all during the run.

  This belongs in Table II.

Model issues:

- **Self-suspension: Partly valid. The logs already answer it, and the draft understated them.** Under RM, the per-frame maximum of (wall − CPU) is **0.01 ms** (p99 0.01) in all four hardware-mode RM runs, not just "0.1 ms on average". The frame task never measurably suspended: codec latency is hidden by pipelining (three frames primed; encoder packets emerge asynchronously). The draft's sentence "self-suspending while it waits for the codec" describes a wait that did not occur here. Remaining caveats: this is an observation, not a bound. IRQ time may be charged to the running thread. Driver and VPU work done outside the thread is not in C.
- **GIL / mailbox blocking: Partly valid. The logs give the evidence the review asks for.** Maximum lateness from release to service start under RM is 0.08–0.09 ms over 4 × 1306 frames, and wall − CPU ≤ 0.01 ms within service. No measurable blocking occurred. That is evidence, not proof: a 5 ms GIL switch interval *could* occur if the detector held the GIL at the wrong moment.
- **Interrupt and driver work outside the measured budget: Confirmed limitation.** Pinning applies to user threads only.
- **Record actual priorities and RT bandwidth: Partly valid.** `set_fifo` fails fast (lines 71–77, `SystemExit` on `PermissionError`), so every RM run that produced a summary did run under FIFO. Thread counts are recorded (`cv_threads`, `codec_threads` = 1). The applied policy is not read back, and neither `sched_rt_runtime_us` nor the 6.18 fair-server settings are recorded. Add these.
- **Harmonic bound: Confirmed** (see 3).

### 5. Energy statistics: Confirmed

- The Mann–Whitney p = 0.41 pooled 22–31 consecutive readings per run as independent observations (`wall_power.txt`, "pooled… Mann-Whitney"). The readings are not independent: lag-1 autocorrelation is −0.70 to −0.75 in three of four runs, because detection bursts alias with the meter's display update. The replicate is the run: n = 2 per governor. Per-run means: ondemand 5.50 and 5.09 W, performance 5.12 and 5.38 W. **Drop the test.** Report the four means and say that no difference was resolved; the spread within a governor (0.4 W) exceeds the difference between governors (0.0 W).
- The equal-work power numbers (6.3 versus 5.3 W) come from **one session** (`20261107T130959`) of "typical value" readings by eye. Both software runs read higher than both hardware runs, but n is 1 session.
- ±0.3 W is our own estimate, not a calibrated accuracy. The meter model is not in any log. **Needed from you: the meter model, its display resolution and its update rate.**
- Keep the 16% and 37% figures, qualified as one session's estimates of outlet-side energy, including the charger and fan.

### 6. Buffer-access experiment: Confirmed on both counts, and the effect attributable to copying is smaller than stated

- **Converter confound.** Exp 03's "convert the copy" uses `cv2.cvtColor`, while "direct" is PyAV/libswscale (`03_frame_access.py` lines 81–87). On ordinary memory the two converters differ by about 1.1 ms (sw: copy + OpenCV 2.86 ms against direct swscale 3.94 ms). That is too small to explain 138 ms, but the "copy first: 138 → 4.4 ms (31.7×)" ratio is not a clean test.
- **Same-converter evidence already in the logs:**
  - Exp 03: hardware direct swscale 138.0 ms against software direct swscale 3.94 ms (35×). Same converter, different buffer.
  - Pipeline v2 (exp 04) uses copy + swscale: 12.2 ms in hardware mode against 7.4 ms in software mode.

  Comparing exp 03's hardware direct path (138 ms) with v2's hardware copy + swscale (12.2 ms) gives a **same-converter copy-first gain of about 11×**, across sessions and core counts. The "factor of 30" in the contributions mixes the converter change with the copy.
- **Power during the early runs.** Exp 03's `sysinfo` shows `throttled=0x50000` (under-voltage and throttling had occurred since boot), and exp 03 kept no clock trace. The pre-fix pipeline runs (`20261106T211822`) had active under-voltage and throttling (`0x50005`, clock down to 600 MHz) in 20 of 210 session samples (19 inside runs):

  | Run | Throttled samples | fps |
  |---|---|---|
  | sw run1 | 12/37 | 9.3 |
  | hw run2 | 6/39 | 4.9 |
  | hw run3 | **0/39** | 5.3 |
  | sw run4 | 1/38 | 11.8 |

  The qualitative result survives in the cleanest pair (hw run3, 5.3 fps, unthrottled, against sw run4, 11.8 fps), but the draft's statement that under-voltage "does not affect the within-run comparisons" is unsupported, and the 9.3–11.8 range includes a throttled run.
- 30× versus 35×: both are arithmetically right (138/4.36 and 138/3.94). State the baseline each time.

### 7. Output equivalence and the software baseline: Partly valid

- **Actual bitrate is in the logs** (`enc_bytes`), and it matches the target. At equal work: software 4.05–4.07 Mb/s, hardware 3.93 Mb/s (−3%). At 30 fps: 4.04 and 4.00 Mb/s. Equal *bitrate* is therefore established within 3%, which answers part of the concern.
- **Quality is not measured** (no PSNR/SSIM, no bitstreams saved). At equal bitrate a hardware encoder usually gives lower quality, which would favour the hardware side of the comparison. This is a real gap.
- Only `veryfast` was tested. "This configured software path cannot meet the deadline" is what we can claim. An `ultrafast` run is a cheap addition.
- v1 draws boxes inline on the same frames in both modes, so the encoder inputs are equivalent up to detector output. In v2 the box timing differs between conditions.

### 8. Presentation and consistency

| Item | Verdict | Evidence |
|---|---|---|
| Fig. 3 extends past 200 s | **Unsupported as a data error** | Run windows are 180.1–180.2 s (section G of the audit output). The x-axis goes to 235 s only to make room for the text labels (`paper_figures.py`, `set_xlim(0, 235)`). Still change it: axis 0–180, labels inside. |
| Fig. 1 looks asynchronous | Confirmed | v1 is inline; v2 is two tasks. Draw both, or label them. |
| Fig. 2 mixes per-call and per-frame | Partly valid | The caption already discloses it ("Detection is per call; one frame in ten"). Show the amortised detection cost (÷10) or separate the panels. |
| Fig. 2 at 15 fps cited for 30 fps | Confirmed | §IV's 30-fps paragraph quotes stage numbers from the 15-fps figure. |
| "Utilization" has two meanings | Confirmed | v1: mean wall service time / period. v2: ΣC/T. Rename the v1 quantity (e.g. "load factor"). |
| CPU time > service time unexplained | Confirmed | Software: 145 ms of CPU per frame against 57.9 ms mean service time. libx264, the decoder and OpenCV's four threads run in parallel. Explain it. |
| Table I mixes sessions | Confirmed | The CPU rows match the four 15-fps sessions (`003226`, `121158`, `125426`, `130959`; the draft says three). Power comes from `130959` only, temperature from `003226` only. Name them. |
| "Repeated runs agreed within about 2%" | Partly valid | True for fps, CPU per frame and v1 load factor (≤1.5% at equal work, ≤1.7% sw at 30 fps). False for the hw 30-fps miss ratio (70.8–75.4%) and for power (5.09–5.50 W with the same governor). State the metric. |
| "All code and data are public" | Confirmed | The repo is private. Author placeholders remain. |

### 9. Governor: Confirmed, and the per-frame logs weaken the claim further

`frames.csv` records the cpufreq frequency at each frame boundary (`scaling_cur_freq_khz`). This is finer than the 0.5 s sampler, but it is still the governor's *requested* frequency.

| Run | Low-clock samples | Detection frames > 145 ms | Starting frequency of those frames |
|---|---|---|---|
| ondemand run1 | 7% | **9** | All 9 began at 900–1100 MHz |
| ondemand run4 | **33%** | **1** | That frame ran at 1.8 GHz throughout |
| performance run2 | 0% | 0 | — |
| performance run3 | 0% | 0 | — |

In run4, detection frames that began or ended at a low clock were not slower (median 124 against 125 ms), despite the most low-clock time.

So the tail effect appears clearly in **one of the two** ondemand runs. Further problems:

- The 145 ms threshold was chosen **after** seeing the data, just above the performance maximum of 144.1 ms. Report p99 and max per run instead: ondemand p99 164.3 and 143.9 ms; performance 138.6 and 137.9 ms.
- "Fixing the clock removes the tail and changes nothing else" and the abstract's "the governor causes the pipeline's longest frames" overclaim.
- Marasini & Zhou show the opposite risk under weaker cooling.
- The performance governor does not override firmware thermal or power limits.

Recommend a fixed clock only for this workload with active cooling.

## 2. Things the review missed

1. v1 misses deadlines at 15 fps (sw 52–54%, hw 20–21%). See 2.
2. The `jobs_released` off-by-one bug. See 4.
3. The pre-fix comparison includes throttled runs. See 6.
4. The copy-first gain with the same converter is about 11×, not about 30×. See 6.
5. The frame task never measurably suspended (max 0.01 ms). The paper should say this, and drop the "waits for the codec" framing. See 4.
6. The abstract's "≈7 °C cooler" comes from **one** matched pair of runs.

## 3. Work, by category

### A. Wording and citations (existing evidence)

1. Separate throughput from deadline compliance everywhere. State the detection cadence. State the v1 miss ratios at 15 fps and 30 fps.
2. Fixed-priority RTA applies only to RM. Call our check retrospective. Put "observed maxima, not WCET" in the abstract, §VII and the conclusion. Use the harmonic bound (1.0) and the 18% slack.
3. Energy: drop Mann–Whitney; report per-run means; write "no difference resolved"; give meter details; call ±0.3 W an estimate; note n = 1 session for equal-work power.
4. Governor: narrow the conclusion; disclose the post-hoc threshold; mention firmware limits; cite Marasini & Zhou as a counterpoint.
5. Related Work section using the verified sources only; reframe contribution 2.
6. Platform paragraph: correct the under-voltage statement.
7. Remove "public" until the repo is public; fill in the author block.

### B. Analysis and figures (existing logs; `review_audit.py` already computes most of this)

1. Rebuild Table II with: nominal / submitted / overwritten / completed (after run) / on time; C_d max; staleness; RTA inputs.
2. Replace the self-suspension and GIL sentences with the max-based evidence.
3. Figures: split Fig. 1 into v1 and v2; Fig. 2 with amortised detection and the stated fps; Fig. 3 axis 0–180.
4. Table I: session map; rename "utilization" for v1; explain CPU time > service time; add a bitrate row.
5. Governor: per-run p99 and max; per-frame frequency attribution.
6. Pre-fix comparison: report the clean pair and flag the throttled runs.

### C. New measurements, in the priority you set

| # | What | Why | Cost (Pi time) |
|---|---|---|---|
| C1 | **Clean buffer experiment** (exp 03 v2): USB-C supply; fan; clock fixed and verified per run (performance governor + `vcgencmd` trace + throttle check). Same converter on both paths: (a) direct swscale vs copy + swscale, (b) OpenCV on both. Check output pixels (exact match or max \|Δ\| ≤ 1). ≥3 sessions, both clips. | Isolates memory handling from the converter; removes the power confound. | ~20 min |
| C2 | **Job accounting in v2**: per nominal job, log release, hand-off, start, end and fate (overwritten, done, done late, never handed over because the frame was not processed). Read back thread policy and priority; log affinity, `sched_rt_runtime_us` and fair-server settings; fix the off-by-one. Then rerun exp 04 (8 runs + 4 with bg). | A clean denominator and an on-time definition. | code + ~40 min |
| C3 | **Calibration, then validation**: 3 calibration runs (hw RM, with and without bg) → freeze C_f and C_d (max) → fresh sessions on another day and on the second clip, compared against the frozen RTA bound. | Turns the consistency check into a prediction. | ~30 min |
| C4 | **Second clip** (`crowd_run`, higher motion, more people): repeat the equal-work comparison (ABBA + power readings) and exp 04 hw RM/default ± bg. Run sessions on ≥3 different days. | Independent replicates; the codec cost depends on content. | ~1 h + power readings |
| C5 | **Power method**: film the meter display with a phone and transcribe with timestamps; per-session means as the replicates (≥3 sessions). | A defensible energy claim without new equipment. | during C4 |
| C6 | **Quality**: save the encoded bitstreams and the raw pre-encode frames for a 10 s segment; PSNR/SSIM with ffmpeg; add one `ultrafast` software run. | Equal output, not just equal bitrate. | ~20 min + PC analysis |

My recommended alternative for C2 (needs your OK): keep the current mechanism, where the detector gets every Nth frame, and fix the *accounting*. A wall-clock timer that hands the detector "the latest processed frame" would change the system being studied and make new runs incomparable with the old ones. Either design is defensible. With the accounting fix, every nominal job gets an explicit fate, including "never handed over".

### D. Optional extensions (for an external venue)

**Frame rate × detection cadence sweep: worth doing, as a prediction test.** With harmonic periods, RM on one core is schedulable under the ideal model iff U = C_f·f + C_d·f/N ≤ 1. From the current hardware maxima (C_f ≈ 24.4 ms, C_d ≈ 305 ms):

| f (fps) | N = 5 | N = 10 | N = 20 | N = 30 |
|---|---|---|---|---|
| 10 | 0.85 | 0.55 | 0.40 | 0.35 |
| 15 | 1.28 ✗ | 0.82 | 0.59 | 0.52 |
| 20 | 1.71 ✗ | 1.10 ✗ | 0.79 | 0.69 |
| 25 | — | 1.37 ✗ | 0.99 (edge) | 0.86 |
| 30 | — | 1.65 ✗ | 1.19 ✗ | 1.04 ✗ |

In software mode the frame task alone (C_f ≈ 117 ms max) caps the frame rate at about 8 fps for any N.

Proposal:

- Measure 6–8 cells around the predicted boundary (e.g. 15/10, 20/10, 20/20, 25/20, 25/30, 30/30) under hw RM, using C budgets frozen from C3, 2 runs each. That is about 40 min.
- Add the default policy ± bg at 2–3 of those cells.
- Run the governor comparison only at the boundary cells.

This sweep would be the strongest new figure: predicted against measured schedulability.

Further options, in rough value order:

- `ultrafast` software preset.
- Pinning IRQs away from core 3 (or `isolcpus`).
- A `PREEMPT_RT` kernel.
- A C reimplementation of the frame task (removes the GIL).
- Pi 5.

## 4. Readiness

**EE654 course paper: adequate after A + B, plus C1** (C1 takes about 20 minutes and the frame-access section depends on it). The flaws are in interpretation and reporting, not in the data. The project exercises the course goals: hardware/software partitioning, timing, energy and thermal trade-offs, RM/RTA on real hardware, and an honest measurement method. A course reviewer would want the wording fixes; none of the findings that survive need new hardware.

**External publication: not ready.** For an arXiv preprint (not peer reviewed), A + B + C1–C4 makes it defensible. For a workshop or student track, add C5, C6, the sweep, and a related-work section built from fully read sources. The novelty is modest: a reproducible case study measuring how the codec path, buffer access, governor and scheduler interact in one complete application. The parts most likely to interest reviewers:

- The same-converter buffer analysis.
- RM against EEVDF under interference, with proper job accounting and staleness.
- The calibrated schedulability-boundary sweep.

**Results that stand as measured:**

- −52% CPU per frame at equal work (four sessions, ≤1.5% spread).
- Hardware sustains 30 fps; software reaches 17.6–17.9 fps.
- Lower die temperature (one matched pair).
- Equal bitrate within 3%.
- Hardware-mode RM on one core: 0 frame misses and all detection jobs on time, with and without background load.
- The default policy holds without load and collapses with two background hogs.
- In software mode RM starves detection and the default policy drags the frame rate down.
- The raw copy from hardware-decoder buffers is 2.5× slower; direct conversion from them is 35× slower with the same converter.

## Sources

- [Marasini & Zhou, arXiv 2609.04705](https://arxiv.org/pdf/2609.04705) (read)
- [Picamera2 issue #740](https://github.com/raspberrypi/picamera2/issues/740) (read via fetch summary)
- [Khernache et al., HAL](https://hal.telecom-paris.fr/LAB-STICC_SHARP/hal-03127340v1) · [X-MOL](https://www.x-mol.com/paper/1348380691536961536) (existence only)
- [VideoCoreCluster, USENIX ATC'16](https://www.usenix.org/conference/atc16/technical-sessions/presentation/liu) · [journal version](https://wings.cs.wisc.edu/publications/videocorecluster-energy-efficient-low-cost-and-hardware-assisted-video-transcoding-system/) (existence only)
- [Bocan et al., MDPI Electronics 15(5):967](https://www.mdpi.com/2079-9292/15/5/967) (indexed, content not read)
- [Linux RT group scheduling](https://docs.kernel.org/scheduler/sched-rt-group.html)

---

## Round 2 (2026-11-11): review of draft v2

Draft v3 (`paper/main.tex`) applies the changes below. It builds to 6 pages with the real IEEEtran class, references included.

| # | Concern | Verdict | Evidence and change |
|---|---|---|---|
| 1 | The deadline endpoint may not be the frame's encoded output | **Confirmed, and material** | Pipeline code: response ends when `enc.encode(frame i)` returns. That call returns packets of *earlier* frames. From `enc_bytes` (initial empty calls plus the key-frame phase; audit §H): libx264 lag 0; `h264_v4l2m2m` lag **2 frames** in v1 (30 and 15 fps) and in v2 under RM, **1 frame** in v2 under `SCHED_OTHER`. Release → encoded output retrieved, median: v1 15 fps hw 148 ms vs sw 72 ms (**the order reverses**: every hw packet is retrieved after one period); v2 hw RM 152 ms (max 158), hw default 100 ms. Decoder latency is excluded in both modes (packets fed from memory on demand). Change: "frame-task response" is defined as CPU job completion; encoder output lag and release → encoded output are reported in Tables I and III, the abstract, §IV, §VII and the conclusion; "zero misses" is narrowed to frame-task (CPU) deadlines. The RM vs SCHED_OTHER conclusion stands for CPU jobs, which is what RTA models. Why the lag depends on the policy is not explained; one hypothesis is stated. |
| 2 | Buffer-copy explanation exceeds the control | **Confirmed** | Adopted the suggested wording. Dropped the "1 ms difference cannot explain" argument. Replaced "the penalty lies mostly in how memory is read" with what *is* controlled: the same routine (libswscale) is 35× slower on the decoder's buffer than on ordinary memory, while a bulk copy is only 2.5× slower. The abstract now says the diagnostic did not isolate the copy's effect. The paired experiment is named and stated as not run. |
| 3 | "Two periodic tasks" | **Confirmed** | Now "a periodic frame task and a frame-triggered detection worker with nominal demand every ten frame periods". RTA and U ≤ 1 are presented as an *idealized reference model*, with the departures listed: release jitter from hand-off, shared mailbox and GIL, codec work outside the threads. Note: in the schedulable hw runs the measured hand-off jitter was 14–16 ms, so these departures are measured rather than unknown. That still does not make the model a guarantee, and the text says so. |
| 4a | Governor: "ran at 1.8 GHz throughout"; "removed the slow frames" | **Confirmed** | Now "the available frequency samples showed 1.8 GHz" and "neither performance run had a detection frame above 145 ms". |
| 4b | Freshness in wall-clock time | **Confirmed; computed from existing logs** | Audit §I. Release of the analysed frame → end of the frame task for the frame showing its boxes, median: hw RM 0.76–0.79 s; hw default + bg **5.8–6.5 s** (max 9.8–11.2 s); sw default 23 s. Added to Table III and §VII. |
| 5 | Traceability | **Confirmed** | `docs/run_manifest.md` maps every paper number to runs and to `review_audit.py` / `paper_figures.py`. The GitHub 404 is expected: the repo is private. It must be made public before the paper's repository sentence is true. The sentence now says "will be public". |
| — | RTA 500.5 vs 500.7 ms | **Confirmed (rounding)** | The text now prints the unrounded inputs (24.421, 305.345 ms): iteration 329.8, 427.5, 476.3, 500.7. |
| — | "Within 3%" | **Confirmed** | 4.05–4.07 vs 3.93 Mb/s is 3.0–3.5%; the text and table now say "3–3.5%". |
| — | "Completed (after run)" label | **Confirmed** | Now "completed (of which after run end)"; the footnote says these jobs *completed* after the timed run ended. |
| — | Page limit | **Resolved** | Course plan: "6-page IEEE paper". v3 is 6 pages including references. The temperature and governor-CDF figures were dropped; their numbers stay in the text and in Table II. |
| — | Controlled buffer comparison as next priority | **Not run (decision)** | Decision of 2026-11-11: no further experiments. The paper no longer claims the copy's effect is isolated, so the claim no longer needs that run. Running it (about 20 min) would let the copy-first effect be stated as measured. |

---

## Round 3 (2026-11-11): review of draft v3

Draft v4 applies the changes below. It is still 6 pages with IEEEtran.

| # | Concern | Verdict | Evidence and change |
|---|---|---|---|
| 1 | Packet-to-frame matching assumes a constant lag and ordered, one-to-one output | **Confirmed; the check found an error in v3** | v3 assumed a constant lag. Per-frame matching (audit §H) shows that in pipeline v1 the hardware lag was **1 frame for the first 240–420 frames, then 2** (one later empty call per run). v2 runs had a constant lag (2 under RM, 1 under SCHED_OTHER). The new method maps the k-th non-empty encoder call to frame k, assuming one packet per frame in order (no B-frames in either encoder). It is validated at every key frame: in every hardware run, every key frame after frame 0 maps to the largest packet in its neighbourhood, and a two-packet call would break every later match. Frame 0, inside warm-up, is small because rate control is still starting. For software (libx264), the lag is 0 for every frame by argument: the first call returns a packet, no later call is empty, and the lag can only grow through an empty call. Effect on the numbers: v1 30 fps median 125–129 ms (v3 said 129); v1 15 fps still 148 ms; v2 unchanged. The paper now calls this the **reconstructed packet-retrieval latency** and states the assumptions. Not done: logging PTS and per-packet timestamps would need an instrumented run, which the "no further experiments" decision excludes. |
| 2 | Release event and decoder buffering | **Confirmed** | The method now defines release precisely: frame i is released at t0 + iT, the scheduled start of its iteration. The iteration then requests the next decoded frame, and the decoder is fed packets from memory whenever it has none ready, so packets enter it before release and their time inside the decoder is not measured (v2 also primes it with 3 frames). Retrieval vs readiness is stated explicitly: the ~152 ms describes this application's retrieval, not the encoder's processing time. |
| 3 | Freshness label | **Confirmed** | Renamed "Box age at encoder submission". The definition is in the footnote, and the §VII text was changed to match. |
| 4 | Buffer experiment as exploratory | **Agreed** | No change needed beyond v3. |
| 5 | Presentation | **Done** | Abstract shortened to 171 words and centred on CPU savings, the latency distinction and the scheduling result; the §VII heading is now "CPU-task schedulability in the tested configuration"; Fig. 4 caption says "Frame-task response times", and its legend no longer covers the rising curve. The repository sentence stays "will be public": the repo must actually be published before submission. |

---

## Round 4 (2026-11-11): final check of draft v4

Draft v5 applies all points: 6 pages with IEEEtran, PDF title and author metadata set, all fonts embedded, no font-type warnings.

| # | Point | Change / evidence |
|---|---|---|
| 1 | Abstract lost the conditions | It now states detection on every tenth frame, equal work at 15 frames/s, energy from one session, and the single-core experiment at 15 frames/s (189 words). |
| 2 | Protocol wording | The A–B–B–A, 90–180 s, at-least-twice protocol is now scoped to the principal comparisons (Sections IV, VI, VII), with Section V's 20 s runs and 150-frame microbenchmark named as exceptions. The governor runs are described as balanced A–B–B–A (ondemand, performance, performance, ondemand). |
| 3 | 138/4.4 ≈ 32 | Now printed with unrounded inputs: 137.97/4.36 ≈ 31.7. The reviewer's 31.4 comes from the rounded inputs; 32 was 31.7 rounded. |
| 4 | Conclusion's two-frame delay | Now reads "under RM". |
| 5 | References [11], [12] | [11] Khernache, Benmoussa, Boukhobza, Menard, J. Systems Architecture vol. 115, art. 102004 (full entry confirmed via the bibliography of arXiv 2401.09854). [12] Liu, Yoon, Kim, Banerjee, Wireless Commun. Mobile Comput. vol. 2018, art. 7470234 (authors and journal from the authors' group page; journal and DOI from the DOAJ record). |
| 6 | Terminology | DVFS, DMA, EEVDF and GOP expanded at first use; p99 defined in the Table II note; the column is now "# >145" with a definition; "never blocks" is now "no appreciable codec or lock blocking was observed in these runs". |
| — | Lag change vs clip loop | **Partly supported** (audit §L). In all 10 v1 hardware runs the lag grew exactly once, always at the call right after an encoder key frame (call ≡ 1 mod GOP). At 15 fps that was the first key frame after the clip first looped in 6 of 8 runs (call 391 = frame 375 + 16) and the third in 2 (call 421). At 30 fps it happened at call 301, before any loop, and at call 481. No decode-stage spike at the loop boundaries in v1. The paper now ties the change to key frames and notes that the loop "may play a part". In v2 (lead 1–2, never a later empty call) there was no change. |
| — | AI acknowledgment | Now names Claude (scripts, analysis, drafting and revision of all sections) and ChatGPT (draft review, related-work suggestions, checked against sources). |
| — | Font warnings | Cause: matplotlib embedded the OTF/CFF font Nimbus Roman as TrueType (Type 42). Figures now use Liberation Serif (TrueType, Times metrics); `pdffonts` shows every font embedded and subset, and poppler reports no warnings. Run IEEE PDF eXpress only if submitting to an IEEE venue. |
| — | Table III placement | Moved so that it floats to the top of the scheduling page; the conclusion is no longer split by it. |
| — | Reproducibility package | Not paper text: make the repo public, tag the commit matching the submitted PDF (e.g. `paper-v1`), and keep the excluded-runs list in `docs/run_manifest.md`. Model: MobileNet-SSD Caffe weights with SHA-256 pinned in `scripts/fetch_model.sh`; versions are in every `sysinfo.txt`. |

---

## Round 5 (2026-11-11): final pass, `paper/paper_final.pdf`

All five points applied, still 6 pages: the governor sentence rewritten as suggested; Section II now says "the simplified models used here" (Audsley et al. handle blocking and jitter); the key-frame check is described as consistency with the assumed mapping, with packet identities not logged; 137.97/4.36 ≈ 31.6; reference [11] is now "M. Bey Ahmed Khernache".
