# Publishing checklist: repository, arXiv, LinkedIn

Order matters: the paper says the code and data "are available at" the GitHub URL, so the repository must be public **before** the PDF goes anywhere.

## 0. Before anything (decisions only you can make)

- [ ] **Course and instructor.** Ask your EE654 instructor whether posting the course paper publicly before grading is fine. Also ask whether they would endorse you on arXiv (step 4). Check the course's policy on AI assistance against the paper's acknowledgment.
- [ ] **Affiliation.** Listing King Abdulaziz University on a preprint is normal for a student; check with your department if unsure.

## 1. Clean the working copy (PC)

```sh
cd ~/Documents/Msc/ee654-pi-energy
rm paper/paper_draft_v*.pdf          # superseded drafts (untracked; also ignored from now on)
git status                            # expect: LICENSE, CITATION.cff, README, docs/, paper/, analysis/, pipeline/ changes
git add -A
git commit -m "Release preparation: final paper, licenses, citation, run manifest, review response"
git push
```

## 2. Remove private emails from the history (done 2026-11-12)

Earlier commits carried two private addresses (a personal Gmail and the Pi's Outlook address). A public repository shows every commit's author email. The history was rewritten with `git filter-repo --mailmap` so that every commit is authored as `Yazeed Alzughaibi <yazeedmalzughaibi@gmail.com>`, the address printed in the paper. A full copy of the pre-rewrite repository is kept outside the repo (`../ee654-pi-energy-backup-20261112`).

Still to do after the rewrite:

```sh
cd ~/Documents/Msc/ee654-pi-energy
git log --format='%an <%ae>' | sort -u      # expect one identity
git push --force origin main                 # overwrite GitHub's history (repo is still private)
git push --force --tags
```

On the Pi, the old clone no longer matches the rewritten history. Delete it and clone again, then set the identity:

```sh
git config user.name  "Yazeed Alzughaibi"
git config user.email "yazeedmalzughaibi@gmail.com"
```

## 3. Make the repository public and tag the release

- [ ] GitHub → repository → Settings → General → Danger Zone → **Change visibility → Public**.
- [ ] Optional, for a citable DOI: log in to zenodo.org with GitHub and switch the repository on under GitHub integration **before** the next step. Every GitHub release then gets a DOI.
- [ ] Create the release on the PC:

  ```sh
  git tag -a paper-v1 -m "Paper as submitted to arXiv"
  git push origin paper-v1
  ```

  Then GitHub → Releases → *Draft a new release* → tag `paper-v1` → attach `paper/paper_final.pdf` → Publish.
- [ ] Open the repo in a private browser window (logged out) and check that the README, `paper/paper_final.pdf` and `docs/run_manifest.md` are visible.

## 4. arXiv

1. **Account:** register at arxiv.org with the email in the paper.
2. **Endorsement:** since January 2026 an institutional email alone does not qualify. On the submission page, arXiv shows an endorsement code when you first submit to a category; send it to someone who has published in that category (your instructor or another KAU faculty member is the natural choice). The category you choose decides who can endorse, so ask first and pick the category accordingly (cs.PF or cs.OS; see `paper/arxiv_metadata.md`).
3. **Source package** (arXiv prefers LaTeX source over a PDF):

   ```sh
   cd ~/Documents/Msc/ee654-pi-energy/paper
   tar czf ee654_arxiv.tar.gz main.tex figs/stages.pdf figs/frame_access.pdf figs/sched_bg.pdf
   ```

   arXiv provides IEEEtran itself; no `.bbl` is needed (the bibliography is inline). The package has been test-built from a clean directory: 6 pages, no errors.
4. **Form:** copy title, abstract, comments, categories and license from `paper/arxiv_metadata.md`.
5. **Check arXiv's preview PDF** before confirming: same 6 pages, figures present, the repository URL works.
6. **Timing:** submissions before 14:00 US Eastern (22:00 Riyadh) on a weekday are announced that evening at 20:00 Eastern (04:00 Riyadh the next morning). Moderation can add a day or two for a first submission.
7. **After it appears:** add the arXiv ID to `CITATION.cff` (`identifiers:`), the README's Paper section, and the GitHub release notes. Commit and push.

Rules worth knowing (2025–26): arXiv bans authors for a year when a paper shows unvetted AI output, such as hallucinated references or leftover chatbot text. All 17 references in this paper were checked against their sources on 2026-11-11/12. Authors bear full responsibility for content however it was produced.

## 5. LinkedIn

Post **after** the arXiv link is live, so the post links to a stable, public page. Drafts are in the conversation; replace the two link placeholders. A figure helps the post: Table III or Fig. 4 from the paper, or the pipeline diagram (Fig. 1), exported as an image.

## 6. Later, if you submit to a peer-reviewed venue

- IEEE permits posting the preprint on arXiv. On acceptance, update the arXiv version with the journal reference and follow IEEE's rules for the accepted version.
- Run the final PDF through IEEE PDF eXpress for that venue.
