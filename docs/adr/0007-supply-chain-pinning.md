# ADR 0007: Pin by digest and SHA; no dependency bot

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-11-23 |
| **Decided by** | LBD |
## Context
Tags move. A re-pointed base-image tag or action tag silently changes what runs. Automated update bots were considered and declined for now.

## Decision
- **Base images**: pinned by multi-arch *index* digest in `copier.yml` (`python_digest`, `uv_image_digest`). `scripts/pin_images.sh` resolves them (dry run by default) on the operator's machine. Until resolved, the value `sha256:PENDING` renders the tag only, and the template release refuses to ship it.
- **GitHub Actions** and **pre-commit hooks**: pinned by 40-character commit SHA with the tag in a comment (`# vX` for actions, `# frozen: vX` for hooks, the format `pre-commit autoupdate --freeze` writes).
- **The shared workflows** are called by projects at the template's release *tag*, because Copier renders the tag, not its commit. Mitigation: a repository ruleset on this repo blocks updating or deleting `v*` tags, so a published tag cannot be moved to different code. The ruleset has **no bypass list**: with a single admin, an admin bypass would exempt the only person who can push, so it would protect nothing. An intended change (very rare) means switching the ruleset off on purpose, acting, and switching it back on; the normal fix for a bad tag is the next tag.
- **Python dependencies**: `uv.lock`, `--locked` everywhere.
- **Tool versions**: uv, trivy, mise and pre-commit hook revs pinned explicitly.
- `scripts/check_pins.py` enforces SHA-pinned actions and hooks, tagged and fully qualified images, agreement between duplicated versions, and (on release) `template_ref` equal to the tag with no PENDING digests.
- **No dependency bot** (Dependabot/Renovate) for now: upgrades are reviewed deliberately, monthly and on advisories.

## Consequences
- Pins go stale without a bot; the maintainer review cadence is part of the release checklist.
- Index digests work on both arm64 (Apple silicon) and amd64 (CI).
