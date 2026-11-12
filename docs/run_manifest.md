# Run manifest: final paper (`paper/paper_final.pdf`) → data → command

Every number in `paper/main.tex` comes from the run folders below (under `data/raw/`). It is recomputed by one of two commands, run from the repo root on the PC:

- **A** = `python3 analysis/review_audit.py > docs/review_audit_numbers.txt` (sections A–K of that file)
- **F** = `python3 analysis/paper_figures.py` (writes `paper/figs/*.pdf` and `paper/figs/figure_numbers.json`)

Raw per-run values are in each run's `summary.json`. Per-frame values are in `frames.csv`, and per-detection-job values in `detect.csv` (pipeline v2).

| Paper item | Runs | Command / section |
|---|---|---|
| Platform, kernel, versions, throttle flags | `sysinfo.txt` in every run folder; `clock.csv` of every session below | `cat`, `scripts/sysinfo.sh` |
| §IV 30 fps: fps, load factor, CPU per frame, frame-task miss ratio | `02_week1_offload/20261107T001714` (fan on; runs 1–4) | `summary.json` per run |
| §IV 30 fps: decode/encode stage means | same | `summary.json` → `stages` |
| §IV 30 fps: encoder output lag (1, then 2), reconstructed packet retrieval median 125–129 ms | same | A §H |
| §IV cooling: no-fan 30 fps runs, 68–72 °C, load factor | `02_week1_offload/20261106T233239` (passive) vs `20261107T001714` | `summary.json` → `temp_c`, `utilization`; flags in `clock.csv` |
| §IV cooling: full-load throttling without fan | `01_thermal_soak/20261106T192712.csv` | read directly |
| Table I CPU rows, load factor, miss ratios ("eight runs per mode, four sessions", spread ≤ 1.5%) | `02_week1_offload/20261107T003226`, `20261107T121158`, `20261107T125426`, `20261107T130959` (runs 1, 4 = sw; 2, 3 = hw) | A §J |
| Table I encoder output lag, reconstructed packet retrieval | same four sessions | A §H |
| §IV lag change at a key frame (6 of 8 runs at the first key frame after the clip loops) | same four sessions + `20261107T001714` | A §L |
| Table I bitrate | same four sessions | A §D |
| Table I power, energy per frame | `02_week1_offload/20261107T130959/wall_power.txt` (one session) | arithmetic in that file's header |
| Fig. 2 stage means | `02_week1_offload/20261107T003226` | F → `stages_15fps` |
| Temperature pair (34.1/34.6 → 36.9/43.5 °C) | `02_week1_offload/20261107T003226` run3_hw, run4_sw + `clock.csv` | F → `temperature_15fps` |
| §V pre-fix pipeline (5.3 vs 11.8 fps, 143 vs 4 ms conversion; throttled runs excluded) | `02_week1_offload/20261106T211822` (runs 3 and 4 clean; 1 and 2 throttled) | `summary.json`; per-run flags from `clock.csv` (`0x50005` samples) |
| Fig. 3 and §V copy, convert and direct timings | `03_frame_access/20261106T215616` | F → `frame_access`; A §E |
| §V sticky flags `0x50000` | `03_frame_access/20261106T215616/sysinfo.txt` | A §E |
| §V v2 copy + libswscale 12.2 / 7.4 ms | `04_rms/20261110T202628` run1, run8 (hw); run4, run5 (sw) | A §E |
| §V v1 to_bgr 8.2 vs 2.9 ms | `02_week1_offload/20261107T003226` | F → `stages_15fps` |
| Table II governor: low-clock share, median, p99, max, > 145 ms, power | `02_week1_offload/20261107T134531` (+ `wall_power.txt`) | A §F |
| §VI per-frame frequency of slow frames | same | A §K |
| Table III frame rows (fps, misses, p99, C_f, C_d, U, RTA) | `04_rms/20261110T202628` (no load, 8 runs) and `04_rms/20261110T204647` (2 background processes, 4 runs) | `summary.json`; table printed by `experiments/04_rms.sh` |
| Table III detection-job accounting (nominal 131, handed over, overwritten, completed, after run end, on time, response max) | same | A §A |
| Table III encoder output lag, reconstructed packet retrieval | same | A §H |
| Table III box age (video frames; at encoder submission) | same | A §C, §I |
| §VII RTA iteration (C_f = 24.421, C_d = 305.345 ms) | `04_rms/20261110T202628/run1_hw-rms/summary.json` → `analysis.using_C_max` | `rta_low()` in `pipeline/run_pipeline_v2.py` |
| §VII hand-off jitter 14–16 ms | same sessions | A §A (`sublag`) |
| §VII suspension and blocking (max wall − CPU 0.01 ms, max start lateness 0.09 ms, 5224 frames) | hw RM runs of both exp 04 sessions | A §B |
| Fig. 4 | `04_rms/20261110T204647` run1 (RM), run2 (default) | F → `sched_bg` |

## Known issues

- `summary.json` → `detect_task.jobs_released` in exp 04 runs made before 2026-11-11 counts indices ≡ 5 (mod 10) instead of the frames actually handed over. It is off by one in `run5_sw-rms`. Use A §A instead.
- Packet retrieval is reconstructed from `enc_bytes` (packet timestamps were not logged): the k-th encoder call that returned output carried frame k. This assumes one packet per frame in submission order. For hardware runs it is validated at every key frame after frame 0 (`match_packets` in `analysis/review_audit.py`).
- Runs not used in the paper (preliminary, superseded or smoke tests): `02_week1_offload/20261106T204009`, `20261106T204706`, `20261106T215838`, `20261106T220413`, `20261106T222312`, `20261106T234758`; `04_rms/20261107T211058`; `00_codec_check/*`.
