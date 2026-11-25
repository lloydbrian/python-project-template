# ADR 0003: Podman only; no Docker

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-11-23 |
| **Decided by** | LBD |
## Context
The team moved from Docker to Podman. Projects generated from this template must not assume Docker anywhere: not in commands, file names, compose files, dev containers or CI.

## Decision
- Build and run with **Podman, rootless**. Files are `.container/Containerfile` and `.containerignore`.
- Image names are **fully qualified** (`docker.io/library/python`, `ghcr.io/astral-sh/uv`), because Podman does not resolve short names by default.
- Local multi-container runs use `podman compose` (podman-compose provider).
- The dev container and the notebooks lab service map the host user to the image user (`keep-id:uid=10001,gid=10001`) with a `:Z` mount, so files stay owned by the developer; VS Code is pointed at Podman with `dev.containers.dockerPath`.
- Scans run on exported archives, so no Docker socket is needed: `podman save --format oci-archive`, unpacked to an OCI layout directory, then `trivy image --input <dir>`. trivy (0.76) reads a layout directory or a docker archive with `--input`, but not an OCI archive file; the local `scan`/`sbom` tasks and the release use the same method, so template CI's container stage exercises what the release runs.
- CI uses the Podman preinstalled on GitHub's Ubuntu runners; the release workflow installs it if a runner image lacks it.
- Host ports are ≥1024 (rootless limitation); the `http_port` question enforces it.

## Alternatives considered
- *Docker Desktop*: root daemon, licensing for larger organisations, against the team decision.
- *Supporting both*: doubles the test matrix and documentation for no team benefit.

## Consequences
- macOS developers run a `podman machine` VM (workstation guide).
- Some third-party tooling assumes a Docker socket; prefer archive-based tools (as with trivy) over enabling the Podman socket.
