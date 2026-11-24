# Contributing to python-project-template

Changes follow the delivery loop in `.delivery-loop.yml`. The maintainer (operator) owns pushes, tags and releases.

## Set up

```bash
mise trust && mise install          # python, uv, trivy, gitleaks, actionlint
uvx pre-commit install
mise tasks                          # list maintainer tasks
```

## Make a change

1. Branch: `git switch -c feat/<short-name>`.
2. Edit `template/` and/or `copier.yml`. Template files end in `.jinja`; anything else is copied verbatim.
3. Iterate with the fast gate: `mise run render-test -- service` (or the variant you touched).
4. For each new rule or gate, add a negative control in `scripts/negative_controls.py` that breaks it and names the check that must fail.
5. Keep the reasoning with the change. Comment non-obvious lines in the template. Update the generated README (`template/README.md.jinja`) when behaviour or a task changes. Add an ADR in `docs/adr/` for a real decision.
6. Add an entry under **Unreleased** in `CHANGELOG.md`.
7. Run the full gate before opening a PR: `mise run template-ci`. Add `REQUIRE_CONTAINER=1 mise run render-test -- service` if you touched the Containerfile, compose, the smoke task or the workflows.

## Rules of thumb

- **Every variant must pass its own gates when generated.** If a change only works for one variant, guard it with a condition (`{% if project_type == "service" %}`).
- **Podman only.** No Docker commands, file names or sockets.
- **Pins stay pinned.** Actions by commit SHA, images by tag plus digest, tools by exact version. `mise run pins` checks this.
- **No secrets, real hostnames or account IDs** in the template, tests, docs or commit messages. Use placeholders such as `SOME_API_KEY` and `example.invalid`.
- **Gates must be able to fail.** Never add `|| true` to a gate.

## Commit messages

[Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`, `chore:`, `ci:`, `refactor:`, `test:`. A breaking change for generated projects (a removed question, a renamed file) uses `feat!:` and a **Breaking** note in the changelog with the migration step.

## Releasing

See [Maintaining the template](README.md#maintaining-the-template) in the README.
