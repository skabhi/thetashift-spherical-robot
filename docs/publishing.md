# Publish this handbook

[Handbook](README.md) · [Contents](SUMMARY.md)

## Live documentation

The handbook is published on **[GitHub Pages](https://skabhi.github.io/thetashift-spherical-robot/)**.
It uses Material for MkDocs for chapter navigation, search, copyable code
blocks, light/dark themes and a responsive layout. Markdown sources stay in
docs/ and are also readable directly on GitHub.

## Automatic publishing

The workflow at `.github/workflows/docs.yml` runs on pushes to main and on
manual dispatch. It installs the pinned builder, checks local links,
builds with `mkdocs build --strict`, uploads the site artifact and deploys
through the GitHub Pages environment. Failed builds do not replace the
previous site. The repository's Pages publishing source is GitHub Actions.

Edit handbook pages under docs/. Keep navigation in mkdocs.yml and
SUMMARY.md consistent when adding or renaming chapters. Do not commit the
site/ build output; it is ignored by Git.

## Build and preview locally

In PowerShell from the repository root:

```powershell
python -m venv .venv-docs
.\.venv-docs\Scripts\python.exe -m pip install -r requirements-docs.txt
.\.venv-docs\Scripts\python.exe tools/check_docs.py
.\.venv-docs\Scripts\python.exe -m mkdocs build --strict
.\.venv-docs\Scripts\python.exe -m mkdocs serve
```

Open the local URL printed by MkDocs. Ctrl+C stops the preview server.
The project-local environment and generated site/ output stay out of Git.
The builder and live website do not change or run firmware on your ESP32.

## Repository organization

- firmware/: board-side code and versioned messages.
- tools/: uploader, trace builder/viewer, timing probe and documentation check.
- tests/: host checks and real-board serial tests.
- docs/: handbook content.
- artifacts/: generated local traces/viewers, ignored by Git.

The uploader copies firmware contents to the device root; device imports
remain unchanged. All documented host commands run from the repository root.

## Optional GitBook sync

The root `.gitbook.yaml` and docs/SUMMARY.md remain available for GitBook
Git Sync. If you choose to connect a separate GitBook space later, map the
repository root on branch main so that its root configuration selects docs/.
The public documentation is currently hosted by GitHub Pages, not GitBook.

## Editing rules

- Match command examples to the current paths and function signatures.
- Say whether a command belongs in PowerShell, robot>, or native >>>.
- Keep one detailed message-contract reference in messages.md.
- Distinguish configured rates from measured results and note timing costs.
- Keep unimplemented motor, radio and storage features clearly identified.

Back to [Handbook introduction →](README.md)
