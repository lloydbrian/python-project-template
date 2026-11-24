# Session handoff: python-project-template v2.0.0

**State:** built, tested and independently reviewed in the build sandbox. Nothing has been pushed, tagged or renamed. The operator runs `docs/RUNBOOK-v2.0.0.md`.

## What changed
- `template-repo-files` was converted in place into a Copier template (renamed `python-project-template` in runbook step 6):
  - variants: `service`, `library` (optional container) and `notebooks`;
  - one source of truth for Python version, tools and digests.
- Shared versioned workflows `python-ci.yml` and `python-release.yml`; template CI and template release workflows.
- Service runtime baseline, supply-chain pin policy, scan-exception policy and the release model without a registry (ADRs 0001–0011).
- `template-repo` becomes a reference app generated from the template (runbook step 8, answers in `template-repo.answers.yml`).

## Decisions recorded (by LBD)
- Copier, converting `template-repo-files` in place.
- Podman only; no Docker anywhere.
- No dependency bot.
- No GHCR or registry publishing.
- Python 3.15 default; 3.14 and 3.13 offered (decided 2026-11-24, after confirming every dependency installs from wheels on 3.15).
- Dependency floors at the latest releases, never below a security fix (2026-11-24).
- Optional AI stack (2026-11-24): LanceDB + sentence-transformers (any Python) or ChromaDB (Python ≤3.14, onnxruntime has no 3.15 wheels), each with pdfplumber and Tavily; ChromaDB's server-only advisories handled as time-boxed exceptions (ADR 0012).
- READMEs stay detailed: every tool and step carries its "why".

## Verification
| Check | Result |
|---|---|
| Render + gates, 8 variants including both AI stacks (lint, format, mypy strict, pytest + coverage, pip-audit, bandit, full-history gitleaks, image-stage simulation) on 3.15, 3.14, 3.13 | 8/8 PASS |
| Negative controls | 22/22 caught |
| `copier update` test (template change arrives, local edit kept, computed ref moves, no conflicts) | PASS |
| actionlint, root pre-commit, gitleaks, pin policy (actions + hooks by SHA, versions agree) | PASS |
| Independent review: correctness, security, operability, docs accuracy | 2 critical (one reported by two reviewers, one found while fixing), 14 major, about 35 minor (unique): all fixed |
| Verifier on the fix commit | 40/41 fixed, 1 partial; 7 low regressions found and fixed |

## Not verified here (and where it will be)
- `podman build`, trivy scans, SBOM and smoke test: the sandbox could not reach the image registries. These run in runbook step 3 (your Mac) and in template CI (`REQUIRE_CONTAINER=1`).
- Base-image digests are `sha256:PENDING` until runbook step 4. The release gate refuses to ship them.
- `python-release.yml` on real runners (arm64, attestations, assets): runbook step 8 does a test release of the reference app.

## Judgment calls (operator)
1. **Shared workflows are called by tag** (`@v2.0.0`), because Copier renders the tag, not its SHA. Mitigation: a tag ruleset blocking updates and deletion (runbook step 6). Fix a bad tag by publishing the next one.
2. **Provenance only on public repos.** Private repos skip attestation (GitHub requires Enterprise Cloud there). Releases still get SBOMs and `SHA256SUMS`.
3. **Residual risk in the notebooks lab:** kernels can edit tracked files. `.git` is read-only; review `git status` after a session (documented).
4. **Old commit metadata:** earlier commits in the repository history carry a personal author email. It predates this work and was not copied anywhere. Rewriting history is destructive, so it is your decision; it only matters if the repo is made public.

## Files for the operator
- `template-repo-files-v2.bundle`: branch `feat/v2-copier-template`.
- `MANIFEST.json`: SHA-256 of every file changed against v1 `main`.
- `SHA256SUMS`: covers the delivery files.
- `RUNBOOK-v2.0.0.md`: the runbook (also in `docs/`).
- `template-repo.answers.yml`: answers for regenerating the reference app.
