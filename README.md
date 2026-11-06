# EE654 Pi Energy Study (v0.3)

**Energy vs. deadlines in a soft real-time video pipeline on the Raspberry Pi 4.**
Course project for EE654 Embedded and Real-Time Systems (Fall 2026).

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
| 02 | `experiments/02_week1_offload.sh` | Week-one test: pipeline v1 in sw vs. hw mode, sustained, with clock trace | ready to run |

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

## Conventions

- README title carries a version number; bump it on every edit.
- Every experiment run saves a `sysinfo.txt` snapshot next to its data.
- Times in logs use the Pi's clock (Asia/Riyadh).

## Changelog

- **v0.3** (2026-11-06): Pipeline v1, experiment 02 (week-one offload test), experiment 01 script, model/input fetch scripts, plot script; setup installs PyAV and OpenCV.
- **v0.2** (2026-11-06): Experiment 00 fixes: fps from frames / wall time (ffmpeg reports 0 for runs under 1 s), `gen_only` baseline so encoder CPU can be separated from test-pattern generation, logs the V4L2 device used.
- **v0.1** (2026-11-05): Initial repo: plan, setup runbook, setup/sysinfo/backup/save scripts, experiment 00.
