# ADR 0002: mise for tools and tasks, uv for Python packaging

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-11-23 |
| **Decided by** | LBD |
## Context
v1 projects mixed pyenv, Make, pip, pip-tools and ad-hoc scripts. Python versions differed between laptops, containers and linters, and "run the checks" meant different things to different people.

## Decision
- **mise** pins the toolchain per repo (`.mise.toml`: Python, uv, gitleaks, trivy) and defines every gate as a task. `mise run ci` (hooks, types, tests, security audit, full-history secret scan) is the single definition of done, used unchanged by CI (`jdx/mise-action`).
- **uv** manages environments, resolution, the lockfile and installs. `uv.lock` is committed; everything automated uses `uv sync --locked`.
- The Python version is one Copier answer feeding mise, `requires-python`, the base image and the ruff and mypy targets.

## Alternatives considered
- *pyenv + Make*: two tools, Make's syntax and portability issues, no tool pinning beyond Python.
- *asdf*: version pinning only, no task runner.
- *Poetry / PDM*: slower resolution; Poetry's own build backend; no Python installation.
- *pip + pip-tools*: no dependency groups, slower, two-step lock workflow.

## Consequences
- Developers install mise and uv once (workstation guide); projects install everything else.
- Tool versions are pinned in places that must agree: copier `uv_version`, `trivy_version` and `gitleaks_version`; the uv-pre-commit hook's `# frozen:` tag; the root `.mise.toml`; and the shared workflows' `mise-version` default. `check_pins.py` enforces all of them.
