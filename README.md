# python-project-template

**One template, three project types, one upgrade path.** This repo generates new Python projects for the team: services, libraries and notebook projects. It keeps them up to date afterwards.

It is a [Copier](https://copier.readthedocs.io/) template. You answer a few questions and get a working repository: pinned toolchain, quality gates, Podman containers, a dev container and CI. When the template improves, `copier update` brings those improvements into every project generated from it, as a reviewable diff.

> **Containers use Podman, not Docker.** Every command, file and CI step in this template assumes Podman (rootless). Docker is not used anywhere.

**Contents:**
[Why it exists](#why-this-template-exists) ·
[Quick start](#quick-start) ·
[Choose a project type](#choose-a-project-type) ·
[Starting an AI project](#starting-an-ai-project) ·
[Questions](#the-questions-copier-asks) ·
[What you get](#what-every-project-gets) ·
[Toolchain and why](#toolchain-and-why-each-tool-was-chosen) ·
[How Copier works](#how-copier-works-here) ·
[Quality gates](#quality-gates) ·
[Container security](#container-security-model) ·
[CI architecture](#ci-architecture) ·
[Releases](#releases-without-a-registry) ·
[Upgrading projects](#upgrading-a-project) ·
[Maintaining](#maintaining-the-template) ·
[Troubleshooting](#troubleshooting) ·
[Layout](#repository-layout) ·
[Decisions](#decisions-adrs) ·
[v1 → v2](#what-changed-from-v1)

---

## Why this template exists

Before this template, every new repo began as a copy of an older one. Each copy drifted. Python versions disagreed between the laptop, the container and the linters. Security checks were written so they could never fail. `.env.dev` files could be committed. Fixes made in one repo never reached the others.

The template removes those failure modes structurally rather than by asking people to remember:

| Problem seen in practice | What the template does about it |
|---|---|
| "Works on my machine", fails in CI | `mise run ci` (hooks, types, tests, security audit, full-history secret scan) is exactly what CI runs before image work, so passing locally means passing in CI |
| Python 3.14 locally, 3.12 in the image, 3.11 in ruff/mypy | One answer (`python_version`) drives mise, `requires-python`, the base image and the ruff/mypy targets |
| Unpinned installs that change under you | `uv.lock` committed; `uv sync --locked` everywhere; base images pinned by digest; CI actions and pre-commit hooks pinned by commit SHA |
| Secrets committed or baked into images | `.env*` ignored except `.env.example`; gitleaks on every commit; secrets only at run time via `podman secret` |
| Security checks that cannot fail (`pip-audit \|\| true`) | Every gate exits non-zero on findings, and negative controls prove each gate can fail |
| Containers running as root, with full capabilities | Rootless Podman, non-root user, pip removed, read-only filesystem and all capabilities dropped for services |
| Copy-pasted scaffolds never receive fixes | Copier records the template version; `copier update` replays new releases onto existing projects |
| CI pipelines duplicated and diverging per repo | Projects call one shared, versioned workflow; pipeline fixes ship as template releases |

---

## Quick start

**Once per machine:** follow [`workstation/README.md`](workstation/README.md). It installs mise, uv, Copier, Podman and VS Code, and explains what each one is for.

**New project:**

```bash
copier copy --vcs-ref v2.0.1 gh:lloydbrian/python-project-template my-project
cd my-project && git init         # git first: bootstrap installs the git hooks
mise trust && mise install && mise run bootstrap      # creates uv.lock, which CI needs committed
cp .env.example .env.dev          # fill values locally; never committed
git add -A && git commit -m "chore: scaffold from python-project-template v2.0.1"
mise run ci                       # everything CI checks, locally
```

The generated `README.md` explains every file, task and decision in that project. It is the developer's day-to-day reference.

**Non-interactive** (scripts, or to repeat a set-up exactly):

```bash
copier copy --vcs-ref v2.0.1 --defaults \
  --data project_name="Ticket Triage" --data project_type=service \
  gh:lloydbrian/python-project-template ticket-triage
```

> `gh:` is Copier shorthand for `https://github.com/`. If the template repo is private, Copier uses your git credentials (`gh auth login` sets these up).

---

## Choose a project type

| | **service** | **library** | **notebooks** |
|---|---|---|---|
| **Build it when** | You ship an HTTP API that runs as a container | You ship importable code (and a CLI) that other projects install | You explore data or models in JupyterLab, with reusable logic kept testable |
| **Runtime stack** | FastAPI, uvicorn, pydantic-settings | typer CLI, plain package (`py.typed`) | JupyterLab, ipykernel, numpy, pandas |
| **Starter code** | `create_app()` factory, `/health/live`, `/health/ready`, request-ID middleware, JSON logging, typed settings | `core.py` with an example function and CLI command | `helpers.py` with tested helpers notebooks import |
| **Container** | Always (hardened `prod` stage) | Optional (`include_container`) | Always (`lab` stage) |
| **Dev container** | Optional (default on) | Only with a container | Optional (default on) |
| **CI** | Gates + image test, scan, SBOM, **smoke test** | Gates (+ image steps if containerised) | Gates + image test, scan, SBOM |
| **Release** | amd64/arm64 OCI archives + SBOM + provenance | Same, if containerised | Same |
| **Notebook hygiene** | — | — | nbstripout, nbQA |
| **AI stack (optional)** | LanceDB or ChromaDB, local embeddings, pdfplumber, Tavily | — | Same choice |

All three share the same toolchain, the same gates and the same upgrade path.

### Starting an AI project

AI is not a fourth project type. Choose **service** for an AI API (retrieval-augmented generation or search) or **notebooks** for AI exploration, then answer `ai_stack`. Copier asks it only for those two types, and asks it before `python_version`. **Why:** the AI stack decides which Python versions can install, so it is answered first.

| `ai_stack` | Pick it when | Trade-off |
|---|---|---|
| `lancedb` (recommended) | You want retrieval and have no specific need for ChromaDB | LanceDB + model2vec embeddings: any offered Python including 3.15, small images, no PyTorch. Its model scores lower on retrieval benchmarks than all-MiniLM-L6-v2 |
| `chromadb` | You specifically need ChromaDB | ChromaDB with its built-in all-MiniLM-L6-v2: Python 3.14 or older. onnxruntime has no 3.15 wheels, so 3.15 is shown disabled and the `python_version` default becomes 3.14 |
| `none` (the default) | The project needs no retrieval | Nothing is added |

Either stack adds:

- a vector store behind one `rag.DocumentStore` interface (`add`, `search`, `count`). **Why:** changing stores later touches one file;
- local embeddings, with the model baked into the image at build time. **Why:** containers never download it, so they work offline;
- `pdfplumber` for PDF text, and Tavily web search (`web_search.py`). The key `TAVILY_API_KEY` goes in `.env.dev` locally (git-ignored) or a Podman secret in containers, never in a committed file;
- with ChromaDB only: time-boxed `.pip-audit-ignore` entries for its server-only advisories, dated by `mise run bootstrap` to expire after 90 days. **Why:** the audit gate stays on and fails again when they expire.

The decision, the alternatives and the trade-offs are in [ADR 0012](docs/adr/0012-ai-stack.md).

**Non-interactive** (the same project type and stack as the `service-ai-lancedb` variant template CI tests):

```bash
copier copy --vcs-ref v2.0.1 --defaults \
  --data project_type=service --data ai_stack=lancedb --data project_name="Ticket Triage" \
  gh:lloydbrian/python-project-template ticket-triage
```

Then follow the [Quick start](#quick-start) from `cd`: `git init`, bootstrap, `.env.dev`, the first commit and `mise run ci`.

---

## The questions Copier asks

Answers are saved in the project's `.copier-answers.yml` and reused by every `copier update`. Change one later with `copier update --data <question>=<value>`.

| Question | Asked when | Default | What it controls |
|---|---|---|---|
| `project_type` | always | `service` | Which files, dependencies, tasks and CI steps are generated |
| `project_name` | always | (required) | Human-readable name: README title, API title, kernel name. No double quotes, backslashes or line breaks (it is written into TOML and Python) |
| `project_slug` | always | from the name, e.g. `ticket-triage` (other characters dropped) | Repo, distribution, CLI command and image name. Lowercase letters, digits and single hyphens; starts with a letter; no trailing hyphen |
| `package_name` | always | slug with `_`, e.g. `ticket_triage` | Python import package under `src/` |
| `description` | always | the project name | `pyproject.toml` and README |
| `author_name` | always | `Lloyd D.` | `pyproject.toml` authors |
| `ai_stack` | service, notebooks | `none` | `lancedb` (LanceDB + model2vec embeddings, any Python, no PyTorch) or `chromadb` (ChromaDB + built-in embedder, Python 3.14 or older), each with pdfplumber and Tavily. Asked before `python_version` because it limits it ([ADR 0012](docs/adr/0012-ai-stack.md)) |
| `python_version` | always | `3.15` (`3.14` with ChromaDB) | One value for mise, `requires-python`, the base image, ruff `target-version` and mypy `python_version`. Choices `3.15`, `3.14`, `3.13`. With `ai_stack=chromadb`, 3.15 is shown disabled with the reason: onnxruntime, which ChromaDB always installs, has no 3.15 wheels yet |
| `github_owner` | always | `lloydbrian` | Where the project's CI finds the shared workflow |
| `coverage_threshold` | always | `80` | `fail_under` for pytest-cov |
| `license` | always | `Proprietary` | `Proprietary` writes no LICENSE file; `MIT` and `Apache-2.0` write the full text |
| `http_port` | service | `8000` | Port used by uvicorn, compose, smoke test and `.env.example`. Must be ≥1024 (rootless Podman cannot bind lower) |
| `include_container` | library | `false` | Adds the Containerfile, scanning, SBOM and image CI to a library (for CLIs you ship as images) |
| `include_devcontainer` | when there is a container | `true` | VS Code dev container on Podman |
| `kernel_display_name` | notebooks | `Python (<slug>)` | Jupyter kernel label. No quotes or backslashes (passed through the shell) |

Validation runs at question time: a slug with capitals, a name with a double quote or a port below 1024 is rejected before any file is written.

**Computed values** are never asked and never saved. They are recalculated on every `copier update`: the template release (`template_ref`), tool versions (uv, trivy, gitleaks, mise) and base-image digests. This is how version bumps reach existing projects without anyone re-answering questions.

---

## What every project gets

```text
my-project/
├── .copier-answers.yml         answers + template version (drives copier update)
├── .mise.toml                  pinned Python, uv, gitleaks (+ trivy) + every task
├── pyproject.toml  uv.lock     metadata, deps, dependency groups, ruff/mypy/pytest/coverage config
├── .pre-commit-config.yaml     hygiene, uv-lock, ruff, gitleaks (+ nbstripout/nbQA), SHA-pinned
├── .gitignore  .env.example    hardened ignores; variable names only
├── .vscode/settings.json       per-repo interpreter + format on save
├── .github/workflows/ci.yml    short caller of the shared, pinned CI workflow
├── src/<package>/  tests/      src layout, strict types, tests that pass from day one
├── docs/adr/  CHANGELOG.md     the project's own decision log and change history
├── README.md                   full developer reference for THIS project
└── (container variants)
    ├── .container/Containerfile    python-base → build → dev / test / prod|lab
    ├── .container/compose.yaml     hardened local run (service) or JupyterLab (notebooks)
    ├── .containerignore  .trivyignore  tools/check_scan_exceptions.py
    ├── .devcontainer/devcontainer.json   (optional) Podman, keep-id mapped to the image user
    └── .github/workflows/release.yml     tag → multi-arch OCI archives + SBOM + provenance
```

Each project passes all of its own gates the moment it is generated. Template CI proves that for every variant on every change.

---

## Toolchain and why each tool was chosen

The generated README has the full table, with alternatives considered. In short:

| Tool | Role | Why |
|---|---|---|
| **Copier** | Generate and update projects | The only mainstream generator that *updates* existing projects (three-way merge), with typed questions, validation and conditional files ([ADR 0004](docs/adr/0004-copier-single-source-template.md)) |
| **mise** | Tool versions + task runner | One file pins Python and CLI tools and defines the gates, identically on laptops and CI ([ADR 0002](docs/adr/0002-mise-and-uv-toolchain.md)) |
| **uv** | Environments, locking, installs | Fast, real cross-platform lockfile, PEP 735 dependency groups, installs Python ([ADR 0002](docs/adr/0002-mise-and-uv-toolchain.md)) |
| **ruff** | Lint + format | One fast tool replacing flake8, isort, pyupgrade and black |
| **mypy --strict** | Types | Catches `None` and `Any` leaks early; pydantic plugin for services |
| **pytest + coverage** | Tests | Hard coverage floor with branch coverage |
| **pre-commit + gitleaks** | Commit-time and CI checks | Problems and secrets stopped before they reach a PR; the full-history scan in CI catches anything committed past the hook |
| **pip-audit + bandit** | Security | Dependency CVEs and insecure code patterns |
| **Podman** | Containers | Rootless and daemonless; the team standard ([ADR 0003](docs/adr/0003-podman-only.md)) |
| **trivy** | Image scan + SBOM | One tool for both; scans exported archives, so no daemon socket is needed ([ADR 0006](docs/adr/0006-vulnerability-scan-policy.md)) |
| **GitHub Actions (reusable)** | CI and release | One pipeline definition, versioned with the template ([ADR 0009](docs/adr/0009-reusable-ci-workflow.md)) |

---

## How Copier works here

```text
copier.yml                      questions, validators, computed values, messages
template/                       every file of a generated project (*.jinja = rendered)
   └── {% if has_container %}.container{% endif %}/   conditional folder: rendered only when true
.copier-answers.yml (in project) _src_path + _commit (the release) + your answers
```

- **`_subdirectory: template`**: only `template/` is copied. This README, the scripts and the workflows in this repo never leak into projects.
- **Conditional files and folders**: a name that renders to empty is skipped. That is how a library gets no `compose.yaml` and a service gets no `notebooks/`.
- **Releases are git tags.** `copier copy` and `copier update` use the newest tag unless `--vcs-ref` says otherwise. Tags must be PEP 440 versions (`v2.0.0`, `v2.1.0-rc.1`), or Copier cannot order them.
- **`copier update`** renders the old release with your answers, diffs it against the new release, and applies that diff to your project as a three-way merge. Your own edits are preserved. Where both sides changed the same lines, you get conflict markers to resolve.
- **Computed values** (`when: false`) are re-evaluated every update, so bumping `uv_version` or a base-image digest here reaches every project on its next update.

---

## Quality gates

Every generated project ships with these gates, and every gate exits non-zero on failure:

| Gate | Command | Fails when |
|---|---|---|
| Hygiene hooks | `pre-commit` | Trailing whitespace, bad YAML/TOML/JSON, merge markers, large files |
| Lockfile | `uv-lock` hook, `uv sync --locked` | `pyproject.toml` changed without `uv.lock` |
| Lint / format | `ruff check`, `ruff format` | Any finding (rules E F I B UP SIM N S RUF) |
| Types | `mypy --strict` | Any type error |
| Tests | `pytest --cov` | A failing test, or coverage below `coverage_threshold` |
| Secrets | `gitleaks` hook (staged) + `gitleaks git` in `mise run ci` (full history) | A token, key or password in any commit, including ones made with `--no-verify` |
| Dependencies | `pip-audit` | A dependency with a published CVE |
| Code security | `bandit` | Insecure patterns in `src/` |
| Image build context | `scripts/image_sim.py` (template CI) | A file the image build or in-image tests need is not copied by the Containerfile, is excluded by `.containerignore`, or a `license-files` entry is missing; or the OS-upgrade layer cannot be refreshed (no `ARG OS_REFRESH` before `apt-get upgrade`, or `mise run image` does not pass it) |
| Image tests | `podman build --target test` | Tests fail inside the image |
| Dependency audit exceptions | `.pip-audit-ignore` (+ exception checker) | An undocumented, undated, expired or over-90-day entry; only listed IDs are ever ignored |
| Image scan | `trivy` (+ exception checker) | Fixable HIGH/CRITICAL; an expired, undocumented or over-90-day exception; or a `trivy.yaml`, VEX file or `TRIVY_*` setting in `.mise.toml` that could bypass the policy |
| Smoke (service) | `mise run smoke` | Health endpoints or request-ID echo fail with the image running read-only, all capabilities dropped |

**Proof that the gates can fail.** `mise run negative-controls` breaks each rule on purpose and requires a *named* check to fail, then restores the project and requires the check to pass again. It covers 25 controls: env-file ignore, secret detection (a token committed with `--no-verify`), coverage floor, settings validation, blank env values falling back to defaults, request-ID sanitising, health contract, API docs hidden in prod, lint, types, lockfile drift, dependency audit, image build context, an OS-upgrade layer that cannot be refreshed (`OS_REFRESH`), expired, undocumented and over-90-day scan exceptions, trivy config and `TRIVY_*` environment bypasses, image and action pin policy, an undated pip-audit exception, the ChromaDB/Python 3.15 guard, paste-unsafe doc commands, and the project-name validator. A gate that has never been seen failing proves nothing.

---

## Container security model

| Layer | Control | Why |
|---|---|---|
| Engine | **Podman, rootless** | No root daemon; a container escape lands as an unprivileged user |
| Image names | **Fully qualified** (`docker.io/library/python`) | Podman does not guess registries; no short-name ambiguity |
| Base | `python:<ver>-slim` **pinned by multi-arch digest**, `apt-get upgrade` at build | A tag can move, a digest cannot; patches applied even between base releases |
| Dev tools | git only in the `dev` stage; venv owned by `app`, never world-writable | Runtime stages stay minimal |
| Package tools | **pip removed** from the image; uv only in the build stage | pip ships vendored copies of urllib3/setuptools that scanners flag, and is not needed at run time |
| Install | `uv sync --locked --no-dev --no-editable` into `/opt/venv` | Exactly the locked runtime deps; no source tree in prod; venv outside the mount point |
| Layers | `UV_NO_CACHE=1`, `.containerignore` | No caches, `.git`, `.venv` or secrets in layers |
| User | **uid 10001 `app`** in every runtime stage, and for the in-image tests | Non-root inside the container too |
| Run (service) | `read_only`, `tmpfs /tmp`, `cap_drop: ALL`, `no-new-privileges`, port bound to `127.0.0.1` | Least privilege; the smoke test runs the image under these same constraints |
| API surface | `/docs`, `/redoc`, `/openapi.json` off when `APP_ENV=prod` | Production does not advertise its full API |
| Notebooks lab | keep-id user mapping, `.git` mounted read-only, port on `127.0.0.1`, token auth on | Kernel code cannot plant git hooks that run on the host |
| Health | Python-based healthcheck | The image deliberately has no curl or wget |
| Scan | trivy: fixable HIGH/CRITICAL fail; exceptions time-boxed with reason, owner and expiry | Accepted risk is re-reviewed instead of living forever |
| Inventory | CycloneDX SBOM per build and release | Know exactly what shipped |
| Provenance | GitHub artifact attestations on release archives and SBOMs, signed by a job that runs no project code | Prove where and how an image was built (`gh attestation verify`). Public repos only |
| Secrets | `podman secret` at run time; never `ENV` or `COPY` | Nothing secret in any layer |

---

## CI architecture

```text
 generated project                          this repo (python-project-template)
 ─────────────────                          ───────────────────────────────────
 .github/workflows/ci.yml  ── uses ──▶  .github/workflows/python-ci.yml@v2.0.1
   with: image, smoke, mise-version          checkout (full history) → mise install → mise run ci
                                             (hooks, types, tests, security, history secret scan)
                                             → podman build --target test → image → scan → sbom
                                             → smoke → upload SBOM

 .github/workflows/release.yml ─ uses ─▶ .github/workflows/python-release.yml@v2.0.1
   on: tag vX.Y.Z                            build job, per arch (amd64, arm64), read-only token:
                                             gates → test stage → image → OCI archive → scan → SBOM
                                             attest job (no project code, id-token): provenance
                                             publish job: SHA256SUMS → GitHub release

                                         .github/workflows/template-ci.yml   (this repo's own CI)
                                             lint (hooks, actionlint, pins, nothing ignored)
                                             render matrix: service, library, library-container,
                                               notebooks, service-ai-lancedb, notebooks-ai-chromadb,
                                               service-py314, service-py313 (each runs its own gates,
                                               the image-context simulation, and with
                                               REQUIRE_CONTAINER=1 image build, scan and smoke)
                                             negative controls · copier update test

                                         .github/workflows/release.yml       (releases the template)
                                             pins --release (template_ref == tag, no PENDING digests)
                                             → template-ci → GitHub release with CHANGELOG notes
```

- **Pinned by release tag.** A project's CI changes only when the project runs `copier update` and the new `template_ref` lands in its `ci.yml`. A template change can never break a project's CI unannounced.
- **Actions and pre-commit hooks pinned by commit SHA**, with the version tag in a comment. `scripts/check_pins.py` enforces this in the lint job.
- **Projects call the shared workflows by release tag** (`@v2.0.1`), because Copier can only render the tag. Protect `v*` tags in this repo with a ruleset that blocks updates and deletion, so a tag cannot be moved to different code (runbook step 6).
- **Least-privilege tokens**: `contents: read` by default. Only the `attest` job gets `id-token: write` and `attestations: write`, and it runs none of the project's code; only `publish` gets `contents: write`.
- **Branch protection**: require the check **`check / check`** (caller job `check` → reusable job `check`).
- **Private template repo**: projects can only call its workflows if *Settings → Actions → General → Access* allows repositories owned by the same user.

---

## Releases without a registry

Decided 2026-11-23 ([ADR 0011](docs/adr/0011-release-artifacts-without-registry.md)): images are **not** pushed to GHCR or any registry. A project release is a GitHub release carrying:

- `<name>-<version>-linux-amd64.oci.tar` and `...-linux-arm64.oci.tar`, built on native runners
- one CycloneDX SBOM per architecture
- `SHA256SUMS`
- a build-provenance attestation for each archive and SBOM, on public repos. Private repos always skip it: GitHub supports attestations there only on Enterprise Cloud, which the template does not assume

```bash
gh release download v0.1.0 -R owner/project
sha256sum -c SHA256SUMS
gh attestation verify ticket-triage-0.1.0-linux-arm64.oci.tar -R owner/project \
  --signer-workflow lloydbrian/python-project-template/.github/workflows/python-release.yml \
  --source-ref refs/tags/v0.1.0
podman load -i ticket-triage-0.1.0-linux-arm64.oci.tar
```

**Why `--signer-workflow`:** the provenance is signed by this template's shared `python-release.yml`, not by a workflow in the project's repo, so `gh` must be told which workflow to trust. `--source-ref` also pins the signature to the release tag. Without them, the check fails on every project release.

Release a project by setting `version` in `pyproject.toml`, then tagging `v<version>`. The workflow refuses a tag whose normalised PEP 440 form differs (`v0.2.0-rc.1` matches `0.2.0rc1` and is published as a pre-release; `v0.2` does not match `0.2.0`).

---

## Upgrading a project

```bash
cd my-project && git switch -c chore/template-update
copier update --skip-answered                 # newest release; or --vcs-ref v2.1.0
git status && git diff                        # review; resolve conflicts and any *.rej files
mise run bootstrap && mise run ci
```

Read this repo's [CHANGELOG](CHANGELOG.md) first when crossing a major version. `scripts/update_test.py` runs in template CI to prove that updates bring template changes, keep local edits, move computed values forward and leave no conflicts on an untouched project.

---

## Maintaining the template

**Day to day:**

```bash
mise trust && mise install
mise run render-test -- service        # fast loop: render one variant and run its gates
mise run template-ci                   # lint, all variants, controls, update test (add REQUIRE_CONTAINER=1 for full CI parity)
REQUIRE_CONTAINER=1 mise run render-test -- service   # include image build, scan and smoke (needs Podman)
```

**Changing the template:**

1. Edit `template/` or `copier.yml`. Keep the "why" next to the change: a comment in the file, a row in the generated README, or an ADR for a real decision.
2. A new question needs a `help` text, a validator if free-form, and a `when` if it only applies to some variants. Add a row to [the questions table](#the-questions-copier-asks).
3. A new rule needs a negative control in `scripts/negative_controls.py`.
4. A new or moved file must be added to the expected-file lists in `scripts/render.py`. If the image build or in-image tests need it, the Containerfile must `COPY` it; `scripts/image_sim.py` fails otherwise.
5. Add a `CHANGELOG.md` entry under *Unreleased*.

**Releasing** (operator):

1. Set `template_ref` in `copier.yml` to **the tag you are about to push**: first the release candidate (`v2.1.0-rc.1`). The release gate requires them to be equal, and projects generated from the rc call `python-ci.yml@v2.1.0-rc.1`, which exists. To bump tools, change `uv_version`, `trivy_version`, `gitleaks_version` and `mise_version` together with the hook `rev`s (SHA + `# frozen:` tag), the shared workflows' `mise-version` default and the root `.mise.toml`. `mise run pins` checks that they agree.
2. `mise run pin-images` (dry run), then `mise run pin-images -- --write`. Review `git diff copier.yml`.
3. `mise run template-ci`, then move the *Unreleased* changelog section under the new version.
4. Merge to `main`, then tag the rc: `git tag v2.1.0-rc.1 && git push origin v2.1.0-rc.1`. `release.yml` verifies pins, runs template CI and creates a pre-release.
5. Update the reference app (`template-repo`) to the rc and check its CI and a test release. Then set `template_ref: v2.1.0`, merge, and tag `v2.1.0`.

There is no dependency bot ([ADR 0007](docs/adr/0007-supply-chain-pinning.md)). Review tool, action and base-image versions monthly and after security advisories.

**Dependency floors** in `template/pyproject.toml.jinja` are the latest releases at each template release, and never below a version with a published security fix. Refresh them every release: check PyPI for the latest versions, then prove the old floors' risk is gone with a `--resolution lowest-direct` resolve audited by pip-audit (a floor only matters when something resolves low, so audit the low end). Each Python choice must install from wheels on macOS arm64 and Linux amd64/arm64: `uv pip compile --only-binary :all: --python-version <ver> --python-platform <platform>`.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `copier: command not found` | `uv tool install copier` (and make sure `~/.local/bin` is on `PATH`) |
| Copier asks for credentials or `repository not found` | The template repo is private: `gh auth login`, or use the SSH URL `git@github.com:lloydbrian/python-project-template.git` |
| `Cannot update: version from last update not detected` | The project's `_commit` is not a PEP 440 tag (for example it was generated from an untagged commit). Run once with `--vcs-ref <tag>` |
| `copier update` refuses: "Destination repository is dirty" | Commit or stash your changes first; updates need a clean tree to merge into |
| Conflicts after update | Resolve the markers like a git merge. Files Copier could not merge leave a `*.rej` next to them |
| `mise ERROR ... not trusted` | `mise trust` in the repo (CI sets `MISE_TRUSTED_CONFIG_PATHS`) |
| Podman cannot connect (macOS) | `podman machine start`; after OS upgrades `podman machine stop && podman machine start` |
| Slow builds or `exec format error` on Apple silicon | Build for your own architecture (the default). CI covers the other one natively |
| Project CI: "workflow was not found" | The `template_ref` tag does not exist yet, or the template repo is private without access granted |
| Release job fails "sha256:PENDING" | Run `mise run pin-images -- --write` and commit before tagging |
| Release `verify` fails "template_ref is ... but the tag is ..." | Set `template_ref` in `copier.yml` to exactly the tag you push (rc tags included), commit, and tag the next version (`-rc.2`); the tag ruleset stops tags being moved |

---

## Repository layout

```text
.
├── copier.yml                    questions, validators, computed values (single source of truth)
├── template/                     everything a generated project contains
├── .github/
│   ├── workflows/python-ci.yml        shared CI that projects call (workflow_call)
│   ├── workflows/python-release.yml   shared release: multi-arch OCI archives, SBOM, provenance
│   ├── workflows/template-ci.yml      this repo's CI: lint, render matrix, controls, update test, release dry run
│   ├── workflows/release.yml          releases the template on a version tag
│   └── CODEOWNERS
├── scripts/
│   ├── render.py                 render a variant (outside this repo) and run its gates
│   ├── image_sim.py              build-context check of the Containerfile without a container engine
│   ├── negative_controls.py      prove every gate can fail
│   ├── update_test.py            prove copier update works
│   ├── release_dry_run.py        run python-release.yml's build steps on a rendered service, no tag
│   ├── check_shell_snippets.py  doc commands stay paste-safe in zsh and bash (no history expansion)
│   ├── check_pins.py             SHA-pinned actions, tagged images, version agreement, release checks
│   ├── pin_images.sh             resolve base-image digests (operator, dry run by default)
│   └── changelog_section.py      release notes from CHANGELOG.md
├── workstation/                  once-per-machine set-up (README) + terminal prompt config
├── polyglot/                     mise baselines for Node.js and Java/Maven repos
├── docs/adr/                     decisions behind this template
├── .mise.toml                    maintainer tools and tasks
├── .pre-commit-config.yaml  ruff.toml  .delivery-loop.yml
├── CHANGELOG.md  CONTRIBUTING.md  SECURITY.md
└── README.md
```

---

## Decisions (ADRs)

| ADR | Decision |
|---|---|
| [0001](docs/adr/0001-record-architecture-decisions.md) | Record decisions as ADRs |
| [0002](docs/adr/0002-mise-and-uv-toolchain.md) | mise for tools and tasks, uv for Python packaging |
| [0003](docs/adr/0003-podman-only.md) | Podman only; no Docker |
| [0004](docs/adr/0004-copier-single-source-template.md) | One Copier template replaces copy-paste templates |
| [0005](docs/adr/0005-src-layout-and-dependency-groups.md) | src layout; PEP 735 dependency groups for tooling |
| [0006](docs/adr/0006-vulnerability-scan-policy.md) | Fail on fixable HIGH/CRITICAL; time-boxed exceptions |
| [0007](docs/adr/0007-supply-chain-pinning.md) | Pin by digest and SHA; no dependency bot |
| [0008](docs/adr/0008-base-image.md) | `python:<ver>-slim`, patched, without pip |
| [0009](docs/adr/0009-reusable-ci-workflow.md) | Projects call one versioned, reusable workflow |
| [0010](docs/adr/0010-service-runtime-baseline.md) | Service baseline: factory, health endpoints, request ID, JSON logs, typed settings |
| [0011](docs/adr/0011-release-artifacts-without-registry.md) | Release OCI archives + SBOM + provenance; no registry |
| [0012](docs/adr/0012-ai-stack.md) | Optional AI stack: LanceDB (any Python) or ChromaDB (≤3.14), local embeddings, pdfplumber, Tavily |

---

## What changed from v1

v1 was two folders (`template-python-projects/`, `template-jupyterlab-projects/`) copied by hand, plus `template-terminal/`.

| v1 | Problem | v2 |
|---|---|---|
| Copy folders with `cp -R`, then rename by hand | Renames missed; no way to receive later fixes | `copier copy` with validated questions; `copier update` for fixes |
| Two near-identical template folders | Every fix made twice, or once and forgotten | One `template/` with `service`, `library` and `notebooks` variants |
| CI defined in each project | Pipelines drift; fixes do not propagate | Projects call `python-ci.yml@<release>` |
| Image tags only (`python:3.14-slim`) | Base could change under the same tag | Multi-arch digests pinned per release (`mise run pin-images`) |
| Actions pinned by tag (`@v4`) | A moved tag runs different code | Commit SHAs, enforced by `check_pins.py` |
| No release path | No defined artifact | Multi-arch OCI archives, SBOM, provenance on a GitHub release |
| Service had only a CLI | Health, request tracing, logging and config added ad hoc per project | `create_app()`, `/health/live`, `/health/ready`, request ID, JSON logs, fail-fast settings |
| Gates assumed to work | Nothing proved a gate could fail | 25 negative controls in template CI |
| Docker files in `.docker/` | Team moved to Podman | `.container/Containerfile` + `compose.yaml`, Podman only (ADR 0003) |
| `.mise-node.toml`, `.mise-java-maven.toml` inside the Python templates | Not Python; `format` used `\|\| true` | Moved to `polyglot/`; Node 26 LTS (no Corepack: Node 25+ dropped it), Java 25 LTS; no masked failures |
| Workstation set-up repeated in each template README | Two copies drifting; stale `openssl readline` build deps | One [`workstation/README.md`](workstation/README.md) |

The reference application [`template-repo`](https://github.com/lloydbrian/template-repo) is now *generated from* this template, not maintained separately.

**Adopting v2 in a v1 project.** Run `copier copy` into a new branch, then the project's gates, and merge. Your git-ignored `.env.dev` survives the copy, as it should. v2 treats blank values in it (`APP_TITLE=`) as unset, so defaults apply, but compare its names with the new `.env.example` and add what is missing (for example `LOG_JSON`, `HTTP_PORT`). List names without showing values: `sed -E 's/=.*/=<hidden>/' .env.dev`.
