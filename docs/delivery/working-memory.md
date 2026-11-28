# Working memory

Decisions and patterns this repository keeps, so later sessions do not re-litigate them. Append only: a changed decision is a new dated entry that names the one it replaces.

## Decisions

- 2026-11-26: Template licensed MIT OR Apache-2.0; generated projects are their owners' to license, no attribution; Sponsor button via Buy Me a Coffee.
- 2026-11-26: Adopt Dependabot fully; this replaces the "no dependency bot" rule of ADR 0007 (see ADR 0013, to be written).
- 2026-11-26: Generated projects get the `dependency_updates` question (default true); their Dependabot covers uv only; template-owned pins stay with copier update.
- 2026-11-26: Ship the work as two PRs: PR A docs and community (no release, merged as #9); PR B Dependabot, released as template v2.1.0.
- 2026-11-26: Quickstart GIF is hosted as a GitHub attachment, not committed; its VHS tape is committed.
- 2026-11-26: This repo's sessions don't touch ASCENT or write instructions for it.
- 2026-11-27: Native Windows is untested; Windows users are assumed to work in a Linux environment (WSL2 or a VM).
- 2026-11-27: Podman clean-ups from this repo touch only this template's images; other projects' images, containers and volumes are left alone.
- 2026-11-27: The template comparison page stays private until the project webpage is live.
- 2026-11-27: Close the comparison gaps: workflow scanning (zizmor) and PyPI publishing for libraries.
- 2026-11-27: Split the gap work: v2.1.0 = Dependabot + zizmor; v2.2.0 = PyPI publishing for libraries.
- 2026-11-27: ADR 0007 stays Accepted; only its Status line changes, to say its "no dependency bot" clause is superseded by ADR 0013.
- 2026-11-27: Every Dependabot updater (this repo and generated projects) uses a 7-day cooldown, the minimum zizmor accepts (see ADR 0013).
- 2026-11-27: zizmor runs offline and any finding fails; its exceptions live in zizmor.yml, each with its reason (see ADR 0014).
- 2026-11-28: Generated projects' Dependabot is lockfile-only: it updates `uv.lock`, and the `pyproject.toml` minimum versions stay with the template (see ADR 0013).

## Patterns adopted

## Patterns rejected

- 2026-11-26: Committing demo GIFs to the repo (too large for the 500 KB gate, and every re-recording grows history).
- 2026-11-26: `vhs publish` (uploads to a third-party host).
