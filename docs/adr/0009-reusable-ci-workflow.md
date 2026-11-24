# ADR 0009: Projects call one versioned, reusable workflow

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-11-23 |
| **Decided by** | LBD |
## Context
v1 put a full CI pipeline in every project. Pipelines drifted, and hardening (SHA pinning, scan policy, SBOM) had to be applied repo by repo.

## Decision
- `python-ci.yml` and `python-release.yml` in this repo are `workflow_call` workflows.
- A generated project's `ci.yml` and `release.yml` are a few lines that call them at `@<template_ref>`, passing `image`, `smoke`, `name`, `target` and `mise-version` from Copier answers and computed values.
- Projects move to a new pipeline only through `copier update`, as a reviewed diff.

## Consequences
- The required status check is named `check / check`.
- If the template repo is private, Actions access must be granted to the owner's repositories.
- Pipeline changes are tested by template CI (render matrix with `REQUIRE_CONTAINER=1`) before release.
