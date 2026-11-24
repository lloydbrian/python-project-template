# ADR 0008: Base image: python:<ver>-slim, patched, without pip

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-11-23 |
| **Decided by** | LBD |
## Context
Options evaluated: `python:<ver>-slim` (Debian), `python:<ver>-alpine`, distroless Python, Chainguard/Wolfi images, and `ubi9/python`.

## Decision
Use `docker.io/library/python:<ver>-slim`, pinned by digest, with `apt-get upgrade` and pip removed, a non-root user (uid 10001), and the venv copied into a fresh `python-base` for the runtime stage.

## Alternatives considered
- *Alpine*: musl breaks or slows many wheels (numpy, pandas, cryptography builds).
- *Distroless*: smaller, but the Python version follows Debian's, multi-stage venv copying is fiddly, and there is no shell for debugging.
- *Chainguard/Wolfi*: very low CVE counts, but version pinning of free images is limited to `latest`.
- *UBI*: heavier, and lags upstream Python releases.

## Consequences
- Some unfixed Debian CVEs remain visible (reported, not blocking; ADR 0006).
- Revisit if scan noise grows or a pinned minimal image becomes available.
