# ADR 0004: One Copier template replaces copy-paste templates

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-11-23 |
| **Decided by** | LBD |
## Context
v1 had two template folders copied with `cp -R` and renamed by hand. Fixes had to be made twice, renames were missed, and existing projects never received improvements.

## Decision
Convert `template-repo-files` in place into a single **Copier** template, renamed `python-project-template`:
- `copier.yml` holds typed questions with validators, and computed values (`when: false`) for versions and digests.
- `template/` holds all project files; conditional file and folder names produce the `service`, `library` and `notebooks` variants.
- Releases are PEP 440 git tags; projects record theirs in `.copier-answers.yml` and move with `copier update`.
- `template-repo` becomes a reference application *generated from* the template, never edited as a template itself.

## Alternatives considered
- *Cookiecutter*: generation only; updates need the separate `cruft` tool and are weaker.
- *GitHub template repositories*: one-time copy, no questions, no updates.
- *Keep copy-paste, add a checklist*: does not solve drift.

## Consequences
- Template CI must render every variant and run each one's gates (`scripts/render.py`), and must prove updates work (`scripts/update_test.py`).
- Tags must parse as PEP 440 versions (`v2.0.0`, `v2.1.0-rc.1`); other tags break `copier update`.
- Computed values let maintainers ship version bumps without asking projects new questions.
