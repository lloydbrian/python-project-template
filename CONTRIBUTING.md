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
   If the image needs a new file, `COPY` it in the Containerfile: `scripts/image_sim.py` (run by every render test) fails otherwise.
5. Keep the reasoning with the change. Comment non-obvious lines in the template. Update the generated README (`template/README.md.jinja`) when behaviour or a task changes. Add an ADR in `docs/adr/` for a real decision.
6. Add an entry under **Unreleased** in `CHANGELOG.md`.
7. Run the full gate before opening a PR: `mise run template-ci`. Add `REQUIRE_CONTAINER=1 mise run render-test -- service` if you touched the Containerfile, compose, the smoke task or the workflows, and `mise run release-dry-run -- <amd64|arm64>` (your machine's arch) if you touched `python-release.yml` or anything the release builds: it runs the release build job's steps on a rendered service without a tag. CI runs it on both arches.

## Your first contribution

New here? Issues labelled [`good first issue`](https://github.com/lloydbrian/python-project-template/labels/good%20first%20issue) are small, self-contained and list what "done" means.

1. Comment on the issue so nobody else starts the same work.
2. Fork the repo, then follow [Set up](#set-up) and [Make a change](#make-a-change) above.
3. For documentation-only changes, `mise run lint` is enough before you open the PR: it runs the hooks, the doc-command check and the pin policy. Anything under `template/` needs `mise run template-ci`.
4. Open the PR against `main` and describe what you changed and how you checked it. CI runs the full template matrix; the maintainer reviews and merges.

Not sure where to start? Open a question with the issue form and say what you would like to work on.

## Rules of thumb

- **Every variant must pass its own gates when generated.** If a change only works for one variant, guard it with a condition (`{% if project_type == "service" %}`).
- **Podman only.** No Docker commands, file names or sockets.
- **Pins stay pinned.** Actions by commit SHA, images by tag plus digest, tools by exact version. `mise run pins` checks this.
- **No secrets, real hostnames or account IDs** in the template, tests, docs or commit messages. Use placeholders such as `SOME_API_KEY` and `example.invalid`.
- **Gates must be able to fail.** Never add `|| true` to a gate.

## Handling a Dependabot PR

Dependabot ([ADR 0013](docs/adr/0013-dependabot-for-actions-hooks-and-python-dependencies.md)) updates this repo's workflows and its root `.pre-commit-config.yaml`. It cannot read `template/`, so:

- **Action PRs** (`ci(deps): ...`): review the release notes, let CI run, merge. Generated projects receive the new actions with the next template release.
- **Hook PRs** (`chore(deps): ...`) fail the lint job until the template copy matches (`check_pins.py`: "differs from the template's"). On the PR branch, copy the new `rev` and `# frozen:` tag into `template/.pre-commit-config.yaml.jinja`, run `mise run template-ci`, and push. For a gitleaks bump, also raise `gitleaks_version` in `copier.yml` and the root `.mise.toml` in the same PR, so the hook and the full-history scan run the same version (`mise run pins` fails until they agree).
- **A zizmor bump** can add an audit that fails CI. Fix the finding in the same PR, or add an exception with its reason to `.github/zizmor.yml` (this repo) or `template/.github/zizmor.yml.jinja` (generated projects).

## Commit messages

[Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`, `chore:`, `ci:`, `refactor:`, `test:`. A breaking change for generated projects (a removed question, a renamed file) uses `feat!:` and a **Breaking** note in the changelog with the migration step.

## License of contributions

Unless you explicitly state otherwise, any contribution you submit for inclusion in this repository is dual-licensed under MIT OR Apache-2.0, as the [README](README.md#license) describes, without any additional terms or conditions.

## Releasing

See [Maintaining the template](README.md#maintaining-the-template) in the README.
