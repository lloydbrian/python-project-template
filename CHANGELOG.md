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
- Template CI: render matrix (8 variants: service, library, library-container, notebooks, the two AI stacks, and the service on 3.14 and 3.13) with an image build-context simulation (`scripts/image_sim.py`), 24 negative controls, `copier update` test, pin policy, actionlint.
- `scripts/pin_images.sh` to pin base images by multi-arch digest (ADR 0007).
- ADRs 0001–0011, CONTRIBUTING, SECURITY, CODEOWNERS, `.delivery-loop.yml`.
- Optional container for libraries (`include_container`).
- `mise run ci` includes pip-audit, bandit and a full-history gitleaks scan, so it equals what CI runs.
- Copier validators reject names, descriptions and kernel names that would break TOML, Python or shell; the slug drops other characters.
- Release scan and SBOM read the shipped OCI archive unpacked to an OCI layout, because trivy cannot read an OCI archive file with `--input`; local `mise run scan`/`sbom` use the same method so template CI covers it (found by the reference app's test release at rc.2; fixed in rc.3).
- Service settings treat blank env values (`APP_TITLE=`, common in v1 `.env.dev` files) as unset, so defaults apply; `app_title` and `app_version` reject empty strings (found adopting v2 in `template-repo` at rc.1; fixed in rc.2).

### Changed
- Workstation set-up consolidated into `workstation/README.md`; terminal config moved to `workstation/terminal/`. Dropped the `openssl readline zlib sqlite` build dependencies (mise installs prebuilt Python).
- Node.js and Java/Maven mise baselines moved to `polyglot/`, updated to Node 26 LTS and Java 25 LTS, the masked `|| true` removed from the Maven format task, and Corepack (no longer shipped from Node 25) replaced by mise-pinned pnpm/yarn.
- GitHub Actions and pre-commit hooks pinned by commit SHA; image names fully qualified; Podman only (ADR 0003).
- Releases: attestation runs in its own job without project code, and is skipped on private repos; rc tags become pre-releases.
- Scan exceptions limited to 90 days; `trivy.yaml`/VEX files refused.
- Dev container and notebooks lab map the host user to `app`; `.git` is read-only in the lab; git hooks are installed on the host only.
- Production services hide `/docs` and `/openapi.json`.
- Python 3.15 is the default (`3.14` and `3.13` remain choices); every dependency installs from wheels on 3.15 on macOS arm64 and Linux amd64/arm64.
- Dependency floors raised to the latest releases. The v1 floors allowed 7 packages with 34 published advisories (jupyterlab, starlette via fastapi, setuptools, nbconvert, jupyterlab-git, pytest, python-dotenv). Major upgrades: mypy 2, pytest 9, pytest-asyncio 1, pandas 3, rich 15, ipykernel 7, setuptools 84.
- Services add `httpx2` to the dev group: Starlette 1.10 deprecates `httpx` as the TestClient backend.
- Doc commands are paste-safe in zsh and bash: text with `!` is single-quoted, and `scripts/check_shell_snippets.py` (in `mise run lint`) rejects regressions.
- mise 2026.11.14 in CI; `packaging` pinned to 26.4 in the release tag check.
- Optional AI stack (`ai_stack`: `lancedb` or `chromadb`) for services and notebooks: vector store, local embeddings baked into images (LanceDB: model2vec potion-retrieval-32M pinned to a commit, no PyTorch; ChromaDB: its built-in all-MiniLM-L6-v2), pdfplumber, Tavily; `python_version` follows it (ChromaDB ≤3.14). ChromaDB's server-only advisories ship as time-boxed `.pip-audit-ignore` entries dated at bootstrap (ADR 0012). Matrix: 8 variants; 24 negative controls.

### Removed
- `template-python-projects/` and `template-jupyterlab-projects/` (replaced by `template/`).
