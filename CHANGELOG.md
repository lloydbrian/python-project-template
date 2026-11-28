# Changelog

All notable changes to python-project-template. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions: [SemVer](https://semver.org/). Tags must be PEP 440 versions (`v2.0.0`, `v2.1.0-rc.1`).

## [Unreleased]

## [2.1.0] - 2026-11-27

### Added
- License: MIT OR Apache-2.0, at the user's option (`LICENSE-MIT`, `LICENSE-APACHE`). Projects generated from the template are the user's own, with no attribution required; their license is still chosen with the `license` question.
- `docs/design-choices.md`: why Podman, no registry and tags that never move, what each costs, how Podman compares with Docker, containerd and Kubernetes, and how a generated project could move to Docker or Kubernetes.
- README opens with the version and license, a recorded quickstart (`docs/demo/quickstart.tape`, re-recordable with VHS), and a "Find your way" table by audience; project metadata and license sections at the end.
- Issue forms (bug, feature, question; blank issues off, security reports routed to private reporting), a "Your first contribution" section in CONTRIBUTING, and a Sponsor button (`.github/FUNDING.yml`).
- Question `dependency_updates` (default `true`): generated projects get `.github/dependabot.yml` that updates `uv.lock` only (`lockfile-only`; weekly, minor and patch grouped, 7-day cooldown). Existing projects receive it on their next `copier update`; answer `false` to opt out (ADR 0013).
- Dependabot for this repo (`.github/dependabot.yml`): GitHub Actions (grouped) and the root pre-commit hooks (one PR per hook), 7-day cooldown (ADR 0013). CONTRIBUTING explains how to finish a hook PR.
- zizmor workflow scanning (v1.33.1, offline, any finding fails) as a pre-commit hook here and in every generated project, with its exceptions in `.github/zizmor.yml`: generated projects may call the template's shared workflows by release tag; any other action must be pinned by SHA (ADR 0014).
- `check_pins.py`: a hook in both this repo's and the template's pre-commit config must use the same rev and frozen tag; the gitleaks hook's tag must match `gitleaks_version`; the template's Dependabot config may list only `uv`, with `lockfile-only`.
- Negative controls (33): `hook-rev-agreement`, `gitleaks-version-agreement`, `dependabot-uv-only`, `dependabot-lockfile-only`, `release-gate`, `dependency-updates-off`, `workflow-scan`, `workflow-scan-pin-scope`. The `service-py313` variant renders with `dependency_updates=false`. The update test proves a project generated before the question receives Dependabot on update, and that answering `false` removes it.

### Upgrade note
- After `copier update` to 2.1.0, the zizmor hook scans every workflow in `.github/workflows`, including ones you added. An action there pinned by tag (`@v4`) fails `mise run ci`: pin it by commit SHA (with the tag in a comment), or add an exception with its reason to `.github/zizmor.yml`.

### Changed
- ADR 0007's "no dependency bot" clause is superseded by ADR 0013; the rest of ADR 0007 stands. The README and the generated README describe the new update flow.

## [2.0.1] - 2026-11-26

### Fixed
- `mise run image` no longer reuses a stale OS-upgrade layer. The base image is pinned by digest, so `--pull=newer` never invalidated the cached `apt-get upgrade` layer, and a local image could keep OS packages from before a security fix while CI (no cache) had it. The Containerfile declares `ARG OS_REFRESH` before the upgrade and `mise run image` passes today's UTC date, so the layer re-runs at most once a day; the in-image test build (`python-ci.yml`, the README command, `scripts/render.py`) and the release build pass it too. The README's scan advice now says to rebuild with `--no-cache` for an OS package. Found in the reference app's local `mise run image` after v2.0.0.
- `mise run pin-images` shows only the lines it changes. `difflib.unified_diff` cannot turn off autojunk, which in a file of 200+ lines (`copier.yml`) treats frequent lines such as `when: false` as junk and showed unchanged lines as changed.
- CHANGELOG 2.0.0 lists ADRs 0001–0012 (0012 was missing).

### Added
- Release dry run: `mise run release-dry-run -- <arch>` (`scripts/release_dry_run.py`) runs the `run:` steps of `python-release.yml`'s build job on a rendered service without a tag (version check, gates, build, OCI export, unpack, scan, SBOM) and checks `dist/` matches the attest job's subjects. Template CI runs it on amd64 and arm64 with a read-only token, so release-path bugs like rc.3's scan fail the PR instead of a tag. It refuses any workflow expression or step key it cannot emulate. `attest` and `publish` still need a real tag.
- Negative control `image-os-refresh` (25 controls): removing `ARG OS_REFRESH` must fail the image build-context check.

### Not changed
- No `jactionlint` step: no such tool exists; `actionlint` already runs in `mise run lint` and template CI.

## [2.0.0] - 2026-11-25

**Breaking:** the repository becomes a Copier template (`python-project-template`). The v1 copy-paste folders are removed. Existing v1 projects can adopt v2 by running `copier copy` into a branch and merging (see the v1 → v2 table in README.md).

### Added
- `copier.yml` with validated questions and three variants: `service`, `library`, `notebooks` (ADR 0004).
- Service runtime baseline: `create_app()` factory, `/health/live`, `/health/ready`, request-ID middleware with log-injection-safe validation, JSON logging, fail-fast typed settings (ADR 0010).
- Shared workflows `python-ci.yml` and `python-release.yml` called by generated projects at a pinned release (ADR 0009).
- Releases without a registry: multi-arch OCI archives, CycloneDX SBOMs, build provenance, `SHA256SUMS` (ADR 0011).
- Time-boxed `.trivyignore` exceptions validated by `tools/check_scan_exceptions.py` (ADR 0006).
- Template CI: render matrix (8 variants: service, library, library-container, notebooks, the two AI stacks, and the service on 3.14 and 3.13) with an image build-context simulation (`scripts/image_sim.py`), 24 negative controls, `copier update` test, pin policy, actionlint.
- `scripts/pin_images.sh` to pin base images by multi-arch digest (ADR 0007).
- README section on starting an AI project: choose `service` or `notebooks`, then `ai_stack`.
- ADRs 0001–0012, CONTRIBUTING, SECURITY, CODEOWNERS, `.delivery-loop.yml`.
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
- Release docs: `gh attestation verify` passes `--signer-workflow` (the template's shared `python-release.yml` signs, not the project's own workflow) and `--source-ref` (found by the reference app's test release at rc.3).
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
