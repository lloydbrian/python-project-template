# ADR 0005: src layout; PEP 735 dependency groups for tooling

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-11-23 |
| **Decided by** | LBD |
## Context
Flat layouts let tests import the working tree instead of the installed package, hiding packaging bugs. v1 put dev tools in `[project.optional-dependencies].dev`, which `uv sync --dev` did not install and which could leak into published metadata.

## Decision
- Code lives in `src/<package>/`; tests import the installed package.
- Tooling lives in `[dependency-groups]` (PEP 735): `dev` (installed by plain `uv sync`), `security`, and `notebooks` for the notebooks variant. Groups never appear in published metadata.
- Optional runtime features stay in `[project.optional-dependencies]`. A service keeps its web framework in `dependencies`, because images install no extras.
- Images install with `--no-dev --no-editable`, so the prod stage contains no source tree.

## Consequences
- `uv sync` gives a complete dev environment; images and CI use `--locked`.
- mypy uses `mypy_path = "src"` and `packages = [...]`; coverage measures the package, not tests.
