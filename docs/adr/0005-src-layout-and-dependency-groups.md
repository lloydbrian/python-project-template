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

## Alternatives considered
- *Flat layout* (package at the repo root): tests import the working tree, so a file missing from the built package still passes tests.
- *Extras for tooling* (`[project.optional-dependencies].dev`): `uv sync --dev` ignores them, and they leak into published metadata as installable extras.

## Consequences
- The notebooks variant sets `[tool.uv] default-groups = ["dev", "notebooks"]`, so `uv sync --locked` in CI does not remove notebook tooling. Image build stages use `--no-default-groups` so no tooling group reaches a runtime image.
- `uv sync` gives a complete dev environment; images and CI use `--locked`.
- mypy uses `mypy_path = "src"` and `packages = [...]`; coverage measures the package, not tests.
