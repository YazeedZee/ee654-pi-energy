# Paper

`main.tex`: IEEE conference format (`IEEEtran`). Figures in `figs/` are generated from the data:

```sh
python3 analysis/paper_figures.py          # from the repo root; writes paper/figs/*.pdf and figure_numbers.json
```

## Building the PDF

- **Overleaf:** new project → upload `main.tex` and the `figs/` folder → compile (IEEEtran is built in).
- **Locally on Debian/Ubuntu:** `sudo apt install texlive-publishers texlive-latex-extra texlive-science texlive-pictures`.
- **Locally on Arch/CachyOS:** `sudo pacman -S texlive-publishers texlive-latexextra texlive-science texlive-pictures`, then `cd paper && latexmk -pdf main.tex`.

## Length

The course requires a 6-page IEEE paper. Draft v3 is 6 pages with the real IEEEtran class, references included. Check the page count after every edit.

## Before publishing

- Author block is filled in (Yazeed Alzughaibi, King Abdulaziz University).
- The introduction points to the GitHub repo: make it public before submitting (check the commit email and add a license).
- Every number in the text should match `figs/figure_numbers.json` or `docs/review_audit_numbers.txt`; regenerate both after any data change.
- Keep the generative-AI disclosure in the Acknowledgment (IEEE policy requires it).
