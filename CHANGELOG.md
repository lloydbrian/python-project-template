# Changelog

All notable changes to python-project-template. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions: [SemVer](https://semver.org/). Tags must be PEP 440 versions (`v2.0.0`, `v2.1.0-rc.1`).

## [Unreleased]

## [2.0.0] - 2026-11-24

**Breaking:** the repository becomes a Copier template (`python-project-template`). The v1 copy-paste folders are removed. Existing v1 projects can adopt v2 by running `copier copy` into a branch and merging (see the v1 → v2 table in README.md).

### Added
- `copier.yml` with validated questions and three variants: `service`, `library`, `notebooks` (ADR 0004).
- Service runtime baseline: `create_app()` factory, `/health/live`, `/health/ready`, request-ID middleware with log-injection-safe validation, JSON logging, fail-fast typed settings (ADR 0010).
- Shared workflows `python-ci.yml` and `python-release.yml` called by generated projects at a pinned release (ADR 0009).
- Releases without a registry: multi-arch OCI archives, CycloneDX SBOMs, build provenance, `SHA256SUMS` (ADR 0011).
- Time-boxed `.trivyignore` exceptions validated by `tools/check_scan_exceptions.py` (ADR 0006).
- Template CI: render matrix (5 variants) with an image build-context simulation (`scripts/image_sim.py`), 19 negative controls, `copier update` test, pin policy, actionlint.
- `scripts/pin_images.sh` to pin base images by multi-arch digest (ADR 0007).
- ADRs 0001–0011, CONTRIBUTING, SECURITY, CODEOWNERS, `.delivery-loop.yml`.
- Optional container for libraries (`include_container`).
- `mise run ci` includes pip-audit, bandit and a full-history gitleaks scan, so it equals what CI runs.
- Copier validators reject names, descriptions and kernel names that would break TOML, Python or shell; the slug drops other characters.

### Changed
- Workstation set-up consolidated into `workstation/README.md`; terminal config moved to `workstation/terminal/`. Dropped the `openssl readline zlib sqlite` build dependencies (mise installs prebuilt Python).
- Node.js and Java/Maven mise baselines moved to `polyglot/`, updated to Node 24 LTS and Java 25 LTS, and the masked `|| true` removed from the Maven format task.
- GitHub Actions and pre-commit hooks pinned by commit SHA; image names fully qualified; Podman only (ADR 0003).
- Releases: attestation runs in its own job without project code, and is skipped on private repos; rc tags become pre-releases.
- Scan exceptions limited to 90 days; `trivy.yaml`/VEX files refused.
- Dev container and notebooks lab map the host user to `app`; `.git` is read-only in the lab; git hooks are installed on the host only.
- Production services hide `/docs` and `/openapi.json`.

### Removed
- `template-python-projects/` and `template-jupyterlab-projects/` (replaced by `template/`).
