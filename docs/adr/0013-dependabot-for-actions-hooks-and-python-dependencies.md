# ADR 0013: Dependabot for this repo's actions and hooks, and for generated projects' Python dependencies

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-11-27 |
| **Decided by** | LBD |

## Context
This ADR supersedes the "no dependency bot" clause of [ADR 0007](0007-supply-chain-pinning.md). The rest of ADR 0007 (pins by digest and SHA, the tag ruleset) stands.

ADR 0007 left upgrades to a monthly manual review. Pins go stale between reviews, and a security fix waits for the next one. OpenSSF Scorecard's Dependency-Update-Tool check rates a repository with no update tool as high risk. Two limits frame the choice: Dependabot cannot read Jinja templates or `copier.yml`, and generated projects call the shared workflows by a tag that `copier update` owns.

## Decision
- **This repo** gets `.github/dependabot.yml`, checked weekly:
  - `github-actions`: every workflow in `.github/workflows`, including the shared `python-ci.yml` and `python-release.yml`. Minor and patch updates are grouped into one PR.
  - `pre-commit`: the root `.pre-commit-config.yaml`, one PR per hook. They are not grouped, because grouped updates of frozen SHAs are unreliable (dependabot-core #15266). Dependabot updates the SHA and the `# frozen:` tag together, so ADR 0007's pin format holds.
- **The template's copies:** Dependabot cannot read `template/`. `scripts/check_pins.py` requires a hook that appears in both configs to use the same rev, so a Dependabot PR fails until the template copy is updated on the same branch. CONTRIBUTING says how.
- **Generated projects:** the question `dependency_updates` (default true) renders `.github/dependabot.yml` covering only `uv` (`uv.lock`), weekly, with minor and patch updates grouped. It sets `versioning-strategy: lockfile-only`, because Dependabot's default for uv also raises the `>=` floors in `pyproject.toml`, which the template owns. Template-owned pins (the dependency floors, the shared-workflow tag, hooks, base-image digests, tool versions) are left out: `copier update` brings them, tested together.
- **Cooldown:** every updater waits 7 days after a release before proposing it (`cooldown: default-days: 7`; Dependabot's own default is 3). A compromised release has a week to be caught and pulled before it reaches a PR, and zizmor's `dependabot-cooldown` audit ([ADR 0014](0014-scan-workflows-with-zizmor.md)) requires at least 7. Security updates are not delayed by a cooldown.
- **Still manual,** monthly and after advisories: the versions and digests in `copier.yml`, the root `.mise.toml` tool versions, and the hooks only the template uses (nbstripout, nbQA), which Dependabot cannot see.
- **Settings:** Dependabot alerts and security updates are switched on in repository settings, here and in each generated project. These are operator steps.

## Alternatives considered
- *Keep no bot (ADR 0007)*: every upgrade stays deliberate, but pins drift between reviews and security fixes wait. Scorecard rates it high risk.
- *Renovate*: considered; the decision is to keep Dependabot, which is built into GitHub and needs no extra app or self-hosting.
- *Dependabot for everything in generated projects*: it would bump the shared-workflow tag and the hooks independently of the template, so projects would drift from what the template tests, and `copier update` would conflict with it.

## Consequences
- **Easier:** action and hook updates arrive as PRs that have already passed the 13 required checks. Fixes for vulnerable Python dependencies in generated projects arrive without waiting for a review.
- **Harder:** a hook PR needs a second commit (the template copy) before it passes, and there are more PRs to review each week.
- **Shifts:** the monthly review shrinks to what Dependabot cannot read: `copier.yml`, `.mise.toml` and the template-only hooks.
