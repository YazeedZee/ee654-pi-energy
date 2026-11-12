# EE654 Pi Energy Study (v0.9)

**Energy vs. deadlines in a soft real-time video pipeline on the Raspberry Pi 4.**
Course project for EE654 Embedded and Real-Time Systems (Fall 2026).

## Paper

**Is Hardware Offload Enough? Energy, Timing, and Scheduling of a Video Analytics Pipeline on the Raspberry Pi 4**
Yazeed Alzughaibi, King Abdulaziz University, 2026. PDF: [`paper/paper_final.pdf`](paper/paper_final.pdf) (TechRxiv DOI to follow).

A 720p decode–detect–overlay–encode pipeline with a person detector, in a software and a hardware codec version:

- Hardware offload raised throughput from 18 to 30 frames/s and cut CPU time per frame by 52% at equal work (15 frames/s).
- Outlet energy per frame fell only about 16%.
- The hardware encoder's packets were retrieved one to two frames later, so latency went up, not down (median 148 ms against 72 ms).
- On one core, rate-monotonic priorities kept every CPU deadline under competing load; the default Linux policy did not.

**Reproducing the numbers.** Every number in the paper maps to run folders and a command in [`docs/run_manifest.md`](docs/run_manifest.md). From the repo root:

```sh
python3 analysis/paper_figures.py                                   # figures + paper/figs/figure_numbers.json
python3 analysis/review_audit.py > docs/review_audit_numbers.txt    # every table value, sections A-L
```

The review history and the corrections it led to are in [`docs/review_response.md`](docs/review_response.md).

**License.** Code: MIT. Data, docs and paper: CC BY 4.0. See [`LICENSE`](LICENSE). Citation: [`CITATION.cff`](CITATION.cff).

The research plan (questions, hypotheses, experimental design, platform record) is in
[`docs/plan.md`](docs/plan.md). How to rebuild the Pi from a blank card is in
[`docs/setup.md`](docs/setup.md).

## Layout

| Path | What goes there | In git? |
|---|---|---|
| `docs/` | Plan, setup runbook, notes | yes |
| `scripts/` | Setup, platform capture, backup, save helpers | yes |
| `experiments/` | One script per experiment (`NN_name.sh`), each writes to `data/raw/NN_name/<timestamp>/` | yes |
| `pipeline/` | The video pipeline code | yes |
| `analysis/` | Python notebooks/scripts that read `data/raw/` and make tables/figures | yes |
| `paper/` | IEEE paper source | yes |
| `data/raw/` | Logs and CSVs from experiment runs (small text) | **yes**: this is the evidence |
| `data/inputs/` | Input videos (large) | **no**: only `README.md` and `SHA256SUMS` are tracked |

## Workflow

```
 PC (analysis, paper) <──git──> GitHub (private) <──git──> Pi (runs experiments)
```

1. **On the Pi:** `git pull`, run an experiment, then `./scripts/save_results.sh` to commit and push the results.
2. **On the PC:** `git pull`, analyse, write.
3. **Rule:** push results at the end of every session. If the card dies, nothing that was pushed is lost.

## If the Pi or its card dies

1. Flash a new card and rebuild following [`docs/setup.md`](docs/setup.md) (about 20 minutes), **or** restore the last card image made with `scripts/backup_card.sh`.
2. Clone the repo; all pushed results are already there.
3. Run `scripts/sysinfo.sh` and compare with the platform record in `docs/plan.md` §4.3. If the kernel or firmware changed, note it in the results log: runs before and after are not directly comparable.

## Experiments

| ID | Script | Purpose | Status |
|---|---|---|---|
| 00 | `experiments/00_codec_check.sh` | Confirm H.264 hardware encode/decode works; first HW vs. SW comparison (no power data) | done 2026-11-06 |
| 01 | `experiments/01_thermal_soak.sh` | 10 min all-core load: does passive cooling throttle? | done 2026-11-06 (ad-hoc; script added after) |
| 02 | `experiments/02_week1_offload.sh` | Week-one test: pipeline v1 in sw vs. hw mode, sustained, with clock trace | smoke tests done; both modes overloaded at N = 3 |
| 03 | `experiments/03_frame_access.py` | Why reading hardware-decoded frames is slow: raw copy vs. conversion | done 2026-11-06 |
| 04 | `experiments/04_rms.sh` | Pipeline v2: two-task rate-monotonic system on one core; default policy vs. RM priorities, with/without background load | done 2026-11-10 |

**Paper:** `paper/` (see `paper/README.md`); figures from `analysis/paper_figures.py`.
**Review response:** `docs/review_response.md`; **run manifest** (paper number → runs → command): `docs/run_manifest.md`; its numbers come from `analysis/review_audit.py` (output in `docs/review_audit_numbers.txt`).

## Pipeline v1

`pipeline/run_pipeline.py`: decode → to_bgr → detect (MobileNet-SSD, every N frames) → overlay → to_yuv → encode,
frames released at 30 fps with a 33.3 ms deadline. `--mode sw` uses software H.264 decode and libx264;
`--mode hw` uses the hardware codec (`h264_v4l2m2m`) for both. The detector runs on the CPU in both modes.
Writes `frames.csv` (per-frame stage times, latency, miss) and `summary.json`.

First-time setup on the Pi:

```sh
sudo ./scripts/setup_pi.sh        # installs python3-av, python3-opencv
./scripts/fetch_model.sh          # detector weights, checksum-verified
./scripts/fetch_inputs.sh         # Xiph clips -> data/inputs/*.mp4
```

## Pipeline v2

`pipeline/run_pipeline_v2.py`: two periodic tasks. Frame task (decode → to_bgr → overlay → to_yuv → encode,
period 1/fps) and detect task (MobileNet-SSD, period N/fps), with rate-monotonic priorities (`--sched rms`:
SCHED_FIFO 80 / 70) or normal Linux scheduling (`--sched cfs`). `--cores 3` pins everything to one core so
the uniprocessor analysis (Liu & Layland bound, response-time analysis) applies; per-job execution time is
measured from thread CPU time. Writes `frames.csv`, `detect.csv`, `summary.json` (with the analysis).
Needs rtprio permission: `sudo ./scripts/setup_pi.sh`, then log in again.

Plots are generated on the PC only (never on the Pi), so the two machines never commit the same file.

## Conventions

- README title carries a version number; bump it on every edit.
- Every experiment run saves a `sysinfo.txt` snapshot next to its data.
- Times in logs use the Pi's clock (Asia/Riyadh).

## Changelog

- **v0.9** (2026-11-12): Release preparation: paper section, licenses (MIT code; CC BY 4.0 data, docs, paper), CITATION.cff, publishing guide (`docs/publishing.md`), preprint metadata (`paper/preprint_metadata.md`).
- **v0.8** (2026-11-11): Run manifest; audit sections H–K (encoder output lag, wall-clock staleness, replicates, per-frame frequency); paper draft v3.
- **v0.7** (2026-11-11): Review audit script and response; paper draft v2; `run_pipeline_v2.py` counts handed-over detection jobs correctly (earlier `summary.json` files keep the old count, off by one in one run).
- **v0.6** (2026-11-10): Paper draft (`paper/`), figure script; experiment 04 done.
- **v0.5** (2026-11-07): Pipeline v2 (two-task RM), experiment 04, rtprio in setup; plots-on-PC rule.
- **v0.4** (2026-11-06): Experiment 03 (frame-access diagnostic); runner reports service time and utilization, runs bounded by wall-clock time.
- **v0.3** (2026-11-06): Pipeline v1, experiment 02 (week-one offload test), experiment 01 script, model/input fetch scripts, plot script; setup installs PyAV and OpenCV.
- **v0.2** (2026-11-06): Experiment 00 fixes: fps from frames / wall time (ffmpeg reports 0 for runs under 1 s), `gen_only` baseline so encoder CPU can be separated from test-pattern generation, logs the V4L2 device used.
- **v0.1** (2026-11-05): Initial repo: plan, setup runbook, setup/sysinfo/backup/save scripts, experiment 00.
