# arXiv submission metadata

Paste these fields into the arXiv submission form. The source package is built by the commands in `docs/publishing.md`, step 4.

**Title**
Is Hardware Offload Enough? Energy, Timing, and Scheduling of a Video Analytics Pipeline on the Raspberry Pi 4

**Authors**
Yazeed Alzughaibi

**Abstract** (plain text, 1213 of 1920 characters)
Single-board computers ship with hardware video codecs, and the usual advice for a video pipeline with deadlines is to use them. We test that advice on a Raspberry Pi 4 running a 720p decode-detect-overlay-encode pipeline with a person detector on every tenth frame. Moving decoding and encoding to the hardware codec raises sustained throughput from 18 to 30 frames/s. At equal work (15 frames/s) it cuts CPU time per frame by 52%, but outlet energy per frame, measured in one session, by only about 16%. Lower CPU time did not mean lower latency: in the way this application collects encoder output, each hardware-encoded packet was retrieved one or two frames after submission, so at 15 frames/s the median time from a frame's release to its encoded packet was 148 ms against 72 ms in software. With detection moved to a separate worker on one core at 15 frames/s, every hardware-mode frame-task and detection job met its CPU deadline under rate-monotonic priorities, with and without competing load, below an idealized response-time estimate; under the default Linux policy, competing load made every frame-task job late. Smaller findings concern slow CPU access to decoder buffers and the frequency governor.

**Comments**
6 pages, 4 figures, 3 tables. Code, raw logs and a run manifest: https://github.com/YazeedZee/ee654-pi-energy

**Primary category:** cs.PF (Performance)
**Cross-lists:** cs.OS (Operating Systems), eess.IV (Image and Video Processing)

Alternative primary category: cs.OS, if your endorser publishes there. The paper's scheduling half fits it as well as cs.PF.

**License:** CC BY 4.0 (matches the repository's license for the paper)

**ACM class (optional):** C.3; D.4.1; D.4.8
(C.3 special-purpose and application-based systems; D.4.1 process management; D.4.8 performance)

**MSC class:** leave empty

**Journal reference / DOI:** leave empty for a preprint
