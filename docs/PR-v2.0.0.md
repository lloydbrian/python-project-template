## python-project-template v2.0.0: one Copier template for every Python project

**Breaking.** `template-repo-files` becomes a Copier template, renamed `python-project-template` after merge. The v1 copy-paste folders are removed.

### Why
- v1 copies drifted.
- Python versions disagreed across the laptop, the image and the linters.
- Some gates could never fail.
- Fixes never reached existing projects.

v2 removes those failure modes structurally. The README's "Why this template exists" section maps each problem to the control that removes it.

### What
- **`copier.yml`**:
  - validated questions;
  - three variants: `service`, `library` (optionally containerised) and `notebooks`;
  - computed tool versions and base-image digests that `copier update` carries forward.
- **Service baseline**:
  - `create_app()`;
  - `/health/live` and `/health/ready`;
  - log-injection-safe request IDs;
  - JSON logs;
  - fail-fast typed settings;
  - API docs hidden in prod.
- **Shared, versioned CI and release workflows**:
  - Podman only;
  - SHA-pinned actions and hooks;
  - full-history secret scan;
  - multi-arch OCI archives, SBOMs and provenance;
  - no registry.
- **Supply chain**:
  - digest pinning via `mise run pin-images`;
  - `check_pins.py` policy;
  - time-boxed scan exceptions, at most 90 days, with no trivy config bypass.
- **Template CI**:
  - 6-variant render matrix, each running its own gates plus an image build-context simulation;
  - 22 negative controls;
  - a `copier update` test.
- **Docs**:
  - root and generated READMEs that explain the *why* of every tool and step;
  - workstation guide (Podman);
  - ADRs 0001–0011;
  - CONTRIBUTING, SECURITY, CHANGELOG and the release runbook.

### Verification
- Gates in the build sandbox:
  - 8/8 variants (Python 3.15 default, 3.14, 3.13, and both AI stacks) pass lint, format, mypy (strict), pytest with coverage, pip-audit, bandit, full-history gitleaks and image-stage simulation;
  - 19/22 negative controls caught;
  - the update test passes;
  - actionlint, pre-commit and the pin policy are clean.
- Independent review covered four lenses (correctness, security, operability, docs accuracy), with a verifier afterwards. All confirmed findings are fixed in `fix: address independent review findings`.
- **Not verified in the sandbox:** real `podman build`, trivy scans, SBOMs and smoke tests, because the registries were unreachable. Runbook step 3 runs them on the Mac, and template CI runs them with `REQUIRE_CONTAINER=1`.

### Operator steps
See `docs/RUNBOOK-v2.0.0.md`:
- pin images;
- rc tag;
- rename;
- tag ruleset;
- regenerate `template-repo`;
- test release;
- v2.0.0.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_017X1tnFjD7kmrvbBErfdgNc
