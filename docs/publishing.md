# Publishing checklist: repository, TechRxiv, LinkedIn

Order matters: the paper says the code and data "are available at" the GitHub URL, so the repository must be public **before** the PDF goes anywhere.

## 0. Before anything (decisions only you can make)

- [x] **Route decided (2026-11-12):** a personal preprint on TechRxiv, with no instructor involvement and no arXiv (arXiv would need an endorser). Code and data get their own DOI through Zenodo.
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

## 4. TechRxiv (the paper)

TechRxiv is IEEE's preprint server for electrical engineering and computing. It is free and needs no endorsement. A moderator screens each submission (not a peer review), and preprints are usually posted within 4 business days with a DOI. Google Scholar indexes it, and IEEE venues accept papers that were posted there first.

1. Create an account and start a new submission.
2. Upload `paper/paper_final.pdf`. Copy the title, abstract and keywords from `paper/preprint_metadata.md`.
3. License: CC BY 4.0 (matches the repository).
4. Post the paper **only here**. A second copy on Zenodo or arXiv would give the same paper two DOIs and split its citations.
5. Once it is posted, add the DOI to `CITATION.cff`, the README's Paper section and the GitHub release notes. Commit and push.
6. Google Scholar: once the paper shows up in Scholar (usually days to weeks), create a Scholar profile and add it.

## 4b. Zenodo (the code and data, optional)

Turn on the repository under Zenodo → GitHub integration **before** creating the `paper-v1` release in step 3. Zenodo then archives that release with its own DOI, which is a permanent snapshot of the code and logs even if GitHub changes.

## 5. LinkedIn

Post **after** the TechRxiv preprint is live, and link its DOI page. The drafts are in the conversation; replace "[arXiv link]" with the TechRxiv link and "[GitHub link]" with the repository. A figure helps the post: Table III or Fig. 4 from the paper, or the pipeline diagram (Fig. 1), exported as an image.

## 6. Later, if you submit to a peer-reviewed venue

- IEEE accepts papers previously posted on TechRxiv. On acceptance, link the published version from the TechRxiv record and follow the venue's rules for the accepted version.
- Run the final PDF through IEEE PDF eXpress for that venue.
