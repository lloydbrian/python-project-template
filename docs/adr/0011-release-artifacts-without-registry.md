# ADR 0011: Release OCI archives + SBOM + provenance; no registry

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-11-23 |
| **Decided by** | LBD |
## Context
Projects need a defined release artifact. Publishing to GitHub Container Registry (GHCR) or another registry was considered and declined: "no need to publish to GHCR" (LBD, 2026-11-23).

## Decision
On a tag matching the project version, `python-release.yml`:
- builds the image natively on `ubuntu-24.04` (amd64) and `ubuntu-24.04-arm` (arm64), after running the gates and the in-image tests;
- exports each as an OCI archive, scans it (same policy as CI) and writes a CycloneDX SBOM;
- records a build-provenance attestation per archive (`actions/attest-build-provenance`);
- publishes archives, SBOMs and `SHA256SUMS` as a GitHub release.

## Consequences
- Consumers run `podman load -i <archive>`, after `sha256sum -c` and `gh attestation verify`.
- No registry credentials exist anywhere in the pipeline.
- If a registry is adopted later, add a push job after the scan; the build, scan and attest steps stay the same. This would need a new ADR superseding this one.
