# Architecture decision records

Decisions behind python-project-template. Format: [ADR 0001](0001-record-architecture-decisions.md).

| ADR | Decision |
|---|---|
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions |
| [0002](0002-mise-and-uv-toolchain.md) | mise for tools and tasks, uv for Python packaging |
| [0003](0003-podman-only.md) | Podman only; no Docker |
| [0004](0004-copier-single-source-template.md) | One Copier template replaces copy-paste templates |
| [0005](0005-src-layout-and-dependency-groups.md) | src layout; PEP 735 dependency groups for tooling |
| [0006](0006-vulnerability-scan-policy.md) | Fail on fixable HIGH/CRITICAL; time-boxed exceptions |
| [0007](0007-supply-chain-pinning.md) | Pin by digest and SHA; no dependency bot |
| [0008](0008-base-image.md) | Base image: python:<ver>-slim, patched, without pip |
| [0009](0009-reusable-ci-workflow.md) | Projects call one versioned, reusable workflow |
| [0010](0010-service-runtime-baseline.md) | Service baseline: factory, health, request ID, JSON logs, typed settings |
| [0011](0011-release-artifacts-without-registry.md) | Release OCI archives + SBOM + provenance; no registry |
| [0012](0012-ai-stack.md) | Optional AI stack, and Python versions that follow it |

To add one: copy the newest ADR, take the next number, set Status to *Proposed*, and open a PR. A decision that reverses an earlier one supersedes it; edit only the old ADR's Status line ("Superseded by ADR NNNN").
