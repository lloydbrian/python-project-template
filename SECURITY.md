# Security policy

## Reporting a vulnerability

Do not open a public issue. Report privately through GitHub's **Security → Report a vulnerability** on this repository (private vulnerability reporting), or contact the owner directly. Include the affected template version (`_commit` in a project's `.copier-answers.yml`) and the variant.

## Supported versions

The latest minor release of the current major version receives fixes. Projects receive them with `copier update`.

## What the template enforces

See [Container security model](README.md#container-security-model) and the ADRs. In short: rootless Podman, non-root users, no pip in images, digest-pinned bases, SHA-pinned actions, gitleaks on commit, pip-audit and bandit, trivy scans that fail on fixable HIGH/CRITICAL, SBOMs, and build provenance on releases.

## Vulnerability exceptions (`.trivyignore`)

An exception is allowed only when a finding cannot be fixed yet **and** the risk is understood. The process:

1. **Try to fix first.** Rebuild with a fresh base (`mise run image` uses `--pull=newer`), upgrade the package (`uv lock --upgrade-package <name>`), or `copier update` to a newer base digest.
2. **Assess.** Is the vulnerable code reachable in this service? Note the reasoning.
3. **Add one line** to `.trivyignore`:
   ```text
   CVE-2026-12345  # reason: <why not exploitable here>; owner: <person or team>; expires: YYYY-MM-DD
   ```
   Keep the expiry short: 30–90 days. More than 90 days ahead is rejected.
4. **Review in the PR.** An exception needs a reviewer other than its author.
5. **On expiry**, the scan fails (`tools/check_scan_exceptions.py`). Fix it, or renew with a fresh assessment and a new date.

Do not add a `trivy.yaml` or VEX file to suppress findings: the checker rejects them, because they would bypass this process.

Undocumented and expired entries fail the build; negative controls in template CI prove that.

## Secrets

- Never commit secrets. `.env*` files other than `.env.example` are ignored, and gitleaks blocks commits containing tokens.
- Supply secrets at run time with `podman secret`, after declaring them into a shell variable with `read -rs NAME` so they are not echoed or kept in shell history.
- If a secret is committed: **rotate it first**, then remove it from history. Removing it from history alone is not enough.
