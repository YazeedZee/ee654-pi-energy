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

| File | Resolution / fps | Motion | Source | Notes |
|---|---|---|---|---|
| *TBD* | 720p30 | low | | |
| *TBD* | 720p30 | high | | |
| *TBD* | 1080p30 | low | | |
| *TBD* | 1080p30 | high | | |
