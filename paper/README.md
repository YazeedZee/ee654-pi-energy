# Paper

`main.tex`: IEEE conference format (`IEEEtran`). Figures in `figs/` are generated from the data:

```sh
python3 analysis/paper_figures.py          # from the repo root; writes paper/figs/*.pdf and figure_numbers.json
```

## Building the PDF

- **Overleaf:** new project → upload `main.tex` and the `figs/` folder → compile (IEEEtran is built in).
- **Locally on Arch/CachyOS:** `sudo pacman -S texlive-publishers texlive-latexextra texlive-science texlive-pictures`, then `cd paper && latexmk -pdf main.tex`.

## Before publishing

- Replace `SURNAME`, `UNIVERSITY, CITY, COUNTRY`, `EMAIL` in the author block.
- The abstract says "All code and data are public": make the GitHub repo public first.
- Keep the generative-AI disclosure in the Acknowledgment (IEEE policy requires it).
