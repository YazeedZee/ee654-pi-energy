# Preprint submission metadata (Zenodo)

Paste these fields into the Zenodo upload form (resource type: Publication → Preprint); upload `paper/paper_final.pdf`. See `docs/publishing.md`, step 4.

**Title**
Is Hardware Offload Enough? Energy, Timing, and Scheduling of a Video Analytics Pipeline on the Raspberry Pi 4

**Authors**
Yazeed Alzughaibi

**Abstract** (plain text, 1213 of 1920 characters)
Single-board computers ship with hardware video codecs, and the usual advice for a video pipeline with deadlines is to use them. We test that advice on a Raspberry Pi 4 running a 720p decode-detect-overlay-encode pipeline with a person detector on every tenth frame. Moving decoding and encoding to the hardware codec raises sustained throughput from 18 to 30 frames/s. At equal work (15 frames/s) it cuts CPU time per frame by 52%, but outlet energy per frame, measured in one session, by only about 16%. Lower CPU time did not mean lower latency: in the way this application collects encoder output, each hardware-encoded packet was retrieved one or two frames after submission, so at 15 frames/s the median time from a frame's release to its encoded packet was 148 ms against 72 ms in software. With detection moved to a separate worker on one core at 15 frames/s, every hardware-mode frame-task and detection job met its CPU deadline under rate-monotonic priorities, with and without competing load, below an idealized response-time estimate; under the default Linux policy, competing load made every frame-task job late. Smaller findings concern slow CPU access to decoder buffers and the frequency governor.

**Comments**
6 pages, 4 figures, 3 tables. Code, raw logs and a run manifest: https://github.com/YazeedZee/ee654-pi-energy

**Keywords:** embedded systems; hardware offload; video processing; energy; DVFS; rate-monotonic scheduling; Raspberry Pi

**Subject areas:** pick the closest entries offered, e.g. Computing and Processing; Signal Processing and Analysis.

**License:** CC BY 4.0 (matches the repository's license for the paper)
