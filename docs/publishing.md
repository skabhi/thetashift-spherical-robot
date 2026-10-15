# Publish this handbook

[Handbook](README.md) · [Contents](SUMMARY.md)

## GitHub: available immediately

The documentation's home is [docs/README.md](README.md). GitHub renders the
Markdown pages, links and tables directly. The repository README links to
this home; each chapter links back to the contents and forward to the next.
Documentation is versioned beside the code and can be reviewed in commits.

The full book navigation is in [SUMMARY.md](SUMMARY.md). Keep each chapter
listed once and update it when adding or renaming a page.

## Optional GitBook site

The repository includes `.gitbook.yaml` at its root, pointing to `docs/`
with README.md as the introduction and SUMMARY.md as navigation. These are
the configuration files used by [GitBook Git Sync](https://gitbook.com/docs/docs-as-code/git-sync/content-configuration).

To host the same book on GitBook, create/select a GitBook documentation
space/site and connect Git Sync to `skabhi/thetashift-spherical-robot`,
branch `main`. Use the repository root as the project/mapped directory so
the root configuration can select docs/. Import the repository's existing
content on the initial sync instead of overwriting it with a blank space.
Review the resulting navigation, then publish from GitBook.

This repository configuration prepares the content; it does not create a
GitBook account, link an organization, or publish a separate hosted site.
Until that connection is made, use the working GitHub handbook link.

## Editing rules

- Keep console examples aligned with current function signatures.
- Say which prompt each command belongs to; do not include prompt text
  inside copyable command blocks.
- Keep one detailed message-contract reference in messages.md.
- Distinguish configured rates from measured results and note timing costs.
- Do not present unimplemented motor, radio or storage features as working.
- After renaming a chapter, update navigation and relative links.

Back to [Handbook introduction →](README.md)
