# Working rules for coding agents in this repository

This repository is `python-project-template`: a Copier template (`template/`, `copier.yml`) plus the shared workflows that generated projects call by tag (`.github/workflows/python-ci.yml`, `python-release.yml`). Read `README.md`, `CONTRIBUTING.md`, `docs/adr/` and `.delivery-loop.yml` before changing anything.

## The operator decides; the agent proves

- **Ask before anything that changes state outside the working tree:** push, tag, merge, PR create or edit, repo rename, settings or rulesets, release create or delete. Show the exact command and what it will change, then wait for a clear yes.
- **Ask before anything destructive, local or remote:** deleting files, branches, tags or releases, `reset --hard`, force-push, `git clean`. Audit first (list exactly what goes), prefer moving over deleting, and confirm afterwards.
- **Pre-flight and post-flight every change:** check the state the step expects before it runs; prove the result after (by the artifact, not by a status line).
- **Every command block is reviewed and tested before it is run or shared.** Write state-changing steps as a shell function: checks first, each failing with `STOP: <reason>` and changing nothing; then the changes joined with `&&`; then one pass line (`<STEP>: OK`). Test it in zsh and bash against a scratch copy of the real state, including the failure cases and a second run.
- **Downloaded deliverables** (patches, checksum files, handoff notes) live in `claude-ai-downloads/` at the repo root, which is git-ignored; `$DL` in `~/.runbook-v2.env` points there. Verify a patch's checksum file before `git am`.
- **No secrets or personal data** in files, commits, logs or chat. Credentials are supplied by the operator at run time (for example `read -rs VAR && export VAR`), never echoed.

## Repository facts that bite

- **Podman only.** No Docker anywhere (ADR 0003).
- **`main` is protected:** changes arrive by PR; 11 required checks, bound to GitHub Actions.
- **Tags never move.** The `release-tags` ruleset blocks updating or deleting `v*` tags, with no bypass (ADR 0007). Fix a bad release with the next tag (`-rc.N+1`, `vX.Y.Z+1`).
- **A release needs `template_ref` in `copier.yml` equal to the tag** (`scripts/check_pins.py --release --tag <tag>`).
- **Gate before delivery:** `mise run template-ci` (renders 8 variants, 25 negative controls, update test; with `REQUIRE_CONTAINER=1` also the release dry run on this machine's arch). Container stages need `REQUIRE_CONTAINER=1` and a running Podman machine.
- **trivy reads a docker archive or an OCI layout directory with `--input`, not an OCI archive file.** Scans unpack the archive first.

## Shell (the operator uses zsh on macOS)

- `!` inside double quotes triggers history expansion: single-quote text such as `'feat!: ...'`.
- macOS `sed -i ''` (BSD), not `sed -i`.
- Pass `-R owner/repo` to `gh` when a clone has more than one remote; set `GH_PAGER=cat` so output prints inline.
- Copier is pinned: `uvx --from copier==9.19.1 copier ...`.
