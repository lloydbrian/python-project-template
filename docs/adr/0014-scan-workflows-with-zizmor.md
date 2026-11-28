# ADR 0014: Scan GitHub Actions workflows with zizmor

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-11-27 |
| **Decided by** | LBD |

## Context
Workflows run with repository permissions and secrets. actionlint checks syntax and types, not security patterns such as template injection, broad permissions or unpinned `uses:`. The comparison of Python templates (2026-11-26) found that three of four peers run zizmor or CodeQL. A trial of zizmor 1.33.1 (2026-11-27, offline) found 1 low finding in this repo, and 2 high in a generated project: its tag-pinned calls to the shared workflows, which are deliberate under [ADR 0007](0007-supply-chain-pinning.md).

## Decision
- **Where it runs:** zizmor runs as a pre-commit hook pinned by SHA (`zizmorcore/zizmor-pre-commit`, `# frozen: v1.33.1`):
  - in this repo, in the lint job on every PR;
  - in the template, so it runs in every generated project's `mise run ci` and on every rendered variant in template CI.
- **How it runs:** offline, so results do not depend on a GitHub token or the network, and generated projects need no setup. Its two online audits (impostor commits, known-vulnerable actions) are skipped; Dependabot alerts ([ADR 0013](0013-dependabot-for-actions-hooks-and-python-dependencies.md)) cover known-vulnerable actions. zizmor uses its default audit level, and any finding fails.
- **Exceptions** live in zizmor's config file, each with its reason:
  - `unpinned-uses`: a generated project may pin `<owner>/python-project-template/.github/workflows/*` by tag. Copier renders a tag, and ADR 0007's ruleset makes it immutable. Every other `uses:` stays pinned by SHA.
  - `self-repository`, in this repo's `release.yml` only: the `$/` syntax is not adopted until GitHub documents it for reusable-workflow calls.
- **Updates:** Dependabot (ADR 0013) keeps the hook current.
- **Proof:** a negative control injects an unsafe workflow expression and requires the zizmor hook to fail.

## Alternatives considered
- *actionlint only (as today)*: no security audits.
- *CodeQL Actions analysis*: hosted by GitHub, with results in the Security tab, but it does not run offline or in pre-commit, so generated projects and local runs would not get it.
- *zizmor as a separate CI job*: it adds a required-check name (a ruleset change) and does not run locally.
- *Fail only on medium and above*: rejected; with the two exceptions in place both this repo and a generated project scan clean, so the stricter bar costs nothing today and catches new low findings early.
- *A stricter audit level*: more findings (concurrency limits, low-confidence template injection). Revisit once the default level is clean.

## Consequences
- **Easier:** unsafe workflow patterns are caught before merge, here and in every generated project.
- **Harder:** a new zizmor version can add audits that fail CI after a Dependabot bump. The fix, or a reasoned exception, lands in that PR.
- **The exception list is reviewed surface:** each entry needs a reason and shows in diffs.
- **One more tool download** (about 10 MB) the first time a machine runs the hooks.
