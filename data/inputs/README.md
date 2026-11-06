# Input videos

Video files are **not** stored in git (too large). This folder tracks only:

- this README: where each input comes from and how it was prepared
- `SHA256SUMS`: checksums, so every run can prove it used identical inputs

After adding or regenerating inputs, update the checksums:

```sh
cd data/inputs && sha256sum *.mp4 > SHA256SUMS
```

Before a measurement session, verify them:

```sh
cd data/inputs && sha256sum -c SHA256SUMS
```

## Inputs

Created by `scripts/fetch_inputs.sh` from the Xiph.org test media collection
(media.xiph.org/video/derf/). Each source is re-timed to 30 fps (no frames dropped
or added) and encoded with libx264: High profile, level 4.1, CRF 20, preset slow,
1-second GOP, yuv420p. Source checksums are in `SOURCES.sha256`.

| File | Resolution / fps | Frames | Content | Source clip |
|---|---|---|---|---|
| `pedestrian_area_720p30.mp4` | 1280×720 / 30 | 375 | people walking, static camera (low motion) | `pedestrian_area_1080p25.y4m` |
| `pedestrian_area_1080p30.mp4` | 1920×1080 / 30 | 375 | same | same |
| `crowd_run_720p30.mp4` | 1280×720 / 30 | 500 | large crowd running (high motion) | `crowd_run_1080p50.y4m` |
| `crowd_run_1080p30.mp4` | 1920×1080 / 30 | 500 | same | same |

Runs longer than a clip loop over it (the pipeline holds the clip in memory).
