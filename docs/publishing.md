# Publishing checklist: repository, Zenodo, LinkedIn

Order matters: the paper says the code and data "are available at" the GitHub URL, so the repository must be public **before** the PDF goes anywhere.

## 0. Before anything (decisions only you can make)

- [x] **Route decided (2026-11-12):** a personal preprint on **Zenodo**, with no instructor involvement. Ruled out:
  - arXiv: needs an endorser.
  - TechRxiv: submissions are closed while it moves to a new platform, with no reopening date.
  - engrXiv: its AI policy forbids generated text used verbatim, and this paper's prose was AI-drafted and then revised.

  Code and data get their own Zenodo DOI from the GitHub release.
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

## 4. Zenodo (code and data first, then the paper)

**4a. Code and data (automatic).** Turn the repository on under Zenodo → GitHub integration **before** creating the `paper-v1` release in step 3. Zenodo archives the release and gives it a DOI (resource type *Software*). Its metadata comes from `CITATION.cff`.

**4b. The paper (manual upload).** Zenodo → New upload:

- **Files:** `paper/paper_final.pdf` only.
- **Resource type:** Publication → Preprint.
- **Title, description (the abstract), keywords:** from `paper/preprint_metadata.md`.
- **Creator:** Yazeed Alzughaibi, with your ORCID and the affiliation King Abdulaziz University.
- **License:** CC BY 4.0.
- **Related works:** "Is supplemented by" → the software DOI from 4a, plus the GitHub URL.
- **Publication date:** the upload date.

Check everything before clicking Publish. A published record cannot be edited away or deleted, only versioned (each new version gets its own DOI under one "concept" DOI). There is no moderation, so the DOI is live immediately.

**Post the paper in one place only.** If TechRxiv reopens later, do not post it there as well: two DOIs for one paper split its citations.

**4c. After publishing:** add both DOIs to `CITATION.cff`, to the README's Paper section and to the GitHub release notes. Commit and push.

**4d. Google Scholar:** once the paper is indexed (days to weeks), create a Scholar profile and add the paper. Until then, use "Add article manually". **ORCID:** Add works → Search & link → DataCite, and pick the Zenodo record.

## 5. LinkedIn

Post **after** the Zenodo record is live, and link its DOI (https://doi.org/10.5281/zenodo.NNNNNNN). The drafts are in the conversation; replace "[arXiv link]" with the DOI link and "[GitHub link]" with the repository. A figure helps the post: Table III or Fig. 4 from the paper, or the pipeline diagram (Fig. 1), exported as an image.

## 6. Later, if you submit to a peer-reviewed venue

- Check the venue's preprint and AI policies first. Many accept papers already posted on Zenodo, but some require the prose to be the authors' own. On acceptance, add a "Is published in" link to the Zenodo record.
- Run the final PDF through IEEE PDF eXpress for that venue.
