#!/usr/bin/env python3
"""Negative controls: break each rule on purpose and prove a NAMED check fails.

A gate that has never been seen failing proves nothing. For every control this script:
  1. runs the check on the pristine render and requires it to PASS,
  2. applies one mutation and requires the check to FAIL with an expected marker
     (a test name, a rule code or a message),
  3. restores the render with git and requires a clean tree and a passing check again.

    python3 scripts/negative_controls.py            # all controls
    python3 scripts/negative_controls.py --offline  # skip the one control that needs PyPI advisories
    python3 scripts/negative_controls.py --list

Standard library only. Needs uv, git and gitleaks on PATH (the root .mise.toml provides them).
"""

from __future__ import annotations

import argparse
import os
import random
import re
import shutil
import string
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = "ref_service"


@dataclass
class Control:
    name: str
    rule: str
    check: str
    mutate: Callable[[Path], None]
    marker: str
    where: str = "render"  # "render" (generated service) or "template" (copy of this repo)
    network: bool = False


def edit(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    if text.count(old) != 1:
        raise SystemExit(f"anchor not found exactly once in {path}: {old!r}")
    path.write_text(text.replace(old, new))


def append(path: Path, text: str) -> None:
    path.write_text(path.read_text() + text)


def template_bot(p: Path) -> Path:
    return next((p / "template/.github").glob("*dependabot.yml*.jinja"))


UNSAFE_JOB = """
  unsafe:
    runs-on: ubuntu-24.04
    permissions: {}
    steps:
      - run: echo "${{ github.event.pull_request.title }}"
"""


def fake_token() -> str:
    # Built at run time so no secret-shaped literal is ever committed to this repo.
    return "ghp_" + "".join(random.choices(string.ascii_letters + string.digits, k=36))


def commit_leak(p: Path) -> None:
    (p / f"src/{PKG}/leak.py").write_text(f'TOKEN = "{fake_token()}"\n')
    subprocess.run(
        "git add -A && git -c user.name=nc -c user.email=nc@example.invalid commit -qm leak --no-verify",
        shell=True,
        cwd=p,
        check=True,
    )


def add_untested_module(p: Path) -> None:
    body = "\n\n".join(
        f"def unused_{i}(x: int) -> int:\n    if x > {i}:\n        return x - {i}\n    return x + {i}"
        for i in range(40)
    )
    (p / f"src/{PKG}/untested.py").write_text(f'"""Deliberately untested."""\n\n\n{body}\n')


CONTROLS = [
    Control(
        "env-files-ignored",
        ".env.dev must never be committable",
        "touch .env.dev; git check-ignore -q .env.dev; rc=$?; rm -f .env.dev; exit $rc",
        lambda p: edit(p / ".gitignore", "\n.env.*\n", "\n"),
        marker="",
    ),
    Control(
        "secret-detection",
        "a token committed past the hook (--no-verify) fails the full-history scan in `mise run ci`",
        "gitleaks git --redact --no-banner .",
        commit_leak,
        marker="leaks found",
    ),
    Control(
        "coverage-floor",
        "coverage below the threshold fails the tests",
        'uv run pytest -q -m "not live"',
        add_untested_module,
        marker="Required test coverage",
    ),
    Control(
        "settings-validation",
        "an unknown LOG_LEVEL fails at start-up",
        'uv run pytest -q --no-cov -m "not live" tests/test_config.py',
        lambda p: edit(
            p / f"src/{PKG}/config.py", 'LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]', "LogLevel = str"
        ),
        marker="test_rejects_unknown_log_level",
    ),
    Control(
        "settings-blank-values",
        "a blank APP_TITLE= in an old env file falls back to the default",
        'uv run pytest -q --no-cov -m "not live" tests/test_config.py',
        lambda p: edit(p / f"src/{PKG}/config.py", ", env_ignore_empty=True)", ")"),
        marker="test_blank_values_use_defaults",
    ),
    Control(
        "request-id-sanitising",
        "unsafe X-Request-ID values are replaced",
        'uv run pytest -q --no-cov -m "not live" tests/test_health.py',
        lambda p: edit(p / f"src/{PKG}/main.py", 're.compile(r"^[A-Za-z0-9._-]{1,64}$")', 're.compile(r".*")'),
        marker="test_request_id_rejects_unsafe_values",
    ),
    Control(
        "health-contract",
        "/health/live reports status ok",
        'uv run pytest -q --no-cov -m "not live" tests/test_health.py',
        lambda p: edit(p / f"src/{PKG}/main.py", 'return {"status": "ok"}', 'return {"status": "up"}'),
        marker="test_live_reports_ok",
    ),
    Control(
        "lint-gate",
        "ruff rejects unused imports",
        "uv run ruff check .",
        lambda p: edit(p / f"src/{PKG}/cli.py", "import typer\n", "import os\n\nimport typer\n"),
        marker="F401",
    ),
    Control(
        "type-gate",
        "mypy strict rejects a wrong return type",
        "uv run mypy",
        lambda p: (p / f"src/{PKG}/typo.py").write_text('def answer() -> int:\n    return "42"\n'),
        marker="Incompatible return value",
    ),
    Control(
        "lockfile-drift",
        "a dependency added without re-locking fails the locked sync",
        "uv sync -q --locked",
        lambda p: edit(p / "pyproject.toml", '"rich>=', '"packaging>=24.0",\n  "rich>='),
        marker="needs to be updated",
    ),
    Control(
        "scan-exception-expiry",
        "an expired .trivyignore entry fails the scan pre-check",
        "uv run python tools/check_scan_exceptions.py .trivyignore",
        lambda p: (p / ".trivyignore").write_text("CVE-2020-0001  # reason: test; owner: qa; expires: 2020-01-01\n"),
        marker="expired",
    ),
    Control(
        "scan-exception-undocumented",
        "a .trivyignore entry without reason/owner/expiry fails",
        "uv run python tools/check_scan_exceptions.py .trivyignore",
        lambda p: (p / ".trivyignore").write_text("CVE-2020-0001\n"),
        marker="needs '# reason",
    ),
    Control(
        "image-pin-policy",
        "a :latest base image fails the pin policy",
        "python3 scripts/check_pins.py --root .",
        lambda p: edit(
            next((p / "template").rglob("Containerfile.jinja")),
            "ghcr.io/astral-sh/uv:{{ uv_version }}",
            "ghcr.io/astral-sh/uv:latest",
        ),
        marker="explicit version tag",
        where="template",
    ),
    Control(
        "action-pin-policy",
        "an action referenced by tag fails the pin policy",
        "python3 scripts/check_pins.py --root .",
        lambda p: (p / ".github/workflows/python-ci.yml").write_text(
            re.sub(
                r"actions/checkout@[0-9a-f]{40}",
                "actions/checkout@v7",
                (p / ".github/workflows/python-ci.yml").read_text(),
                count=1,
            )
        ),
        marker="not pinned to a commit SHA",
        where="template",
    ),
    Control(
        "dependency-audit",
        "a dependency with a known CVE fails pip-audit",
        "uv run --group security pip-audit",
        lambda p: (
            edit(p / "pyproject.toml", '"rich>=', '"jinja2==3.1.2",\n  "rich>='),
            subprocess.run("uv lock -q && uv sync -q --locked", shell=True, cwd=p, check=True),
        ),
        marker="Found",
        network=True,
    ),
    Control(
        "image-build-context",
        "a file the in-image tests need but the Containerfile never copies fails the build simulation",
        f"python3 {ROOT}/scripts/image_sim.py .",
        lambda p: edit(p / ".container/Containerfile", "COPY tools ./tools\n", ""),
        marker="FileNotFoundError",
    ),
    Control(
        "image-os-refresh",
        "an OS-upgrade layer that cannot be refreshed (no ARG OS_REFRESH before apt-get upgrade) fails the build check",
        f"python3 {ROOT}/scripts/image_sim.py .",
        lambda p: edit(p / ".container/Containerfile", "ARG OS_REFRESH=unset\n", ""),
        marker="no `ARG OS_REFRESH` before `apt-get upgrade`",
    ),
    Control(
        "prod-api-docs",
        "production does not serve /docs or /openapi.json",
        'uv run pytest -q --no-cov -m "not live" tests/test_health.py',
        lambda p: edit(p / f"src/{PKG}/main.py", 'docs = settings.app_env != "prod"', "docs = True"),
        marker="test_api_docs_hidden_in_prod",
    ),
    Control(
        "scan-exception-horizon",
        "an exception dated more than 90 days ahead fails the scan pre-check",
        "uv run python tools/check_scan_exceptions.py .trivyignore",
        lambda p: (p / ".trivyignore").write_text("CVE-2020-0001  # reason: test; owner: qa; expires: 2099-01-01\n"),
        marker="more than 90 days",
    ),
    Control(
        "scan-config-bypass",
        "a trivy.yaml (which trivy reads silently) fails the scan pre-check",
        "uv run python tools/check_scan_exceptions.py .trivyignore",
        lambda p: (p / "trivy.yaml").write_text("scan:\n  skip-dirs: [opt/venv]\n"),
        marker="not allowed",
    ),
    Control(
        "scan-env-bypass",
        "TRIVY_* settings in .mise.toml (which trivy reads from the environment) fail the scan pre-check",
        "uv run python tools/check_scan_exceptions.py .trivyignore",
        lambda p: (p / ".mise.toml").write_text((p / ".mise.toml").read_text() + '\n[env]\nTRIVY_SKIP_DIRS = "opt"\n'),
        marker="TRIVY_",
    ),
    Control(
        "audit-exception-undated",
        "a pip-audit exception that was never dated by bootstrap fails the audit pre-check",
        "uv run python tools/check_scan_exceptions.py .pip-audit-ignore",
        lambda p: (p / ".pip-audit-ignore").write_text(
            "PYSEC-2026-1  # reason: test; owner: qa; expires: on-bootstrap\n"
        ),
        marker="not dated",
    ),
    Control(
        "chroma-python-guard",
        "ChromaDB with Python 3.15 is refused at question time (onnxruntime has no 3.15 wheels)",
        "! ${COPIER:-uvx --from copier==9.19.1 copier} copy --defaults --quiet --vcs-ref HEAD"
        " --data project_name=x --data ai_stack=chromadb --data python_version=3.15 . $(mktemp -d)/x",
        lambda p: edit(
            p / "copier.yml",
            "{% if ai_stack == 'chromadb' and project_type != 'library' %}ChromaDB needs",
            "{% if false %}ChromaDB needs",
        ),
        marker="",
        where="template",
    ),
    Control(
        "doc-command-history-expansion",
        'a doc command with "!" in double quotes (zsh: illegal modifier) fails the doc lint',
        "python3 scripts/check_shell_snippets.py",
        lambda p: (
            (p / "docs" / "zsh-trap.md").write_text('```bash\ngit commit -m "feat!: breaks in zsh"\n```\n'),
            subprocess.run("git add docs/zsh-trap.md", shell=True, cwd=p, check=True),
        ),
        marker="would be history-expanded",
        where="template",
    ),
    Control(
        "name-validator",
        "a project name that would break TOML/Python is refused at question time",
        "! ${COPIER:-uvx --from copier==9.19.1 copier} copy --defaults --quiet --vcs-ref HEAD"
        " --data 'project_name=a\"b' --data description=ok . $(mktemp -d)/x",
        lambda p: edit(p / "copier.yml", "{% elif '\"' in project_name", "{% elif false and '\"' in project_name"),
        marker="",
        where="template",
    ),
    Control(
        "hook-rev-agreement",
        "a hook bumped in the root config only (as Dependabot does) fails until the template copy matches",
        "python3 scripts/check_pins.py --root .",
        lambda p: (p / ".pre-commit-config.yaml").write_text(
            re.sub(
                r"(astral-sh/ruff-pre-commit\n\s+rev: )[0-9a-f]{40}",
                r"\g<1>" + "0" * 40,
                (p / ".pre-commit-config.yaml").read_text(),
            )
        ),
        marker="differs from the template",
        where="template",
    ),
    Control(
        "dependabot-uv-only",
        "generated projects' Dependabot may update uv.lock only; template-owned pins come with copier update",
        "python3 scripts/check_pins.py --root .",
        lambda p: template_bot(p).write_text(
            template_bot(p).read_text()
            + "  - package-ecosystem: github-actions\n    directory: /\n    schedule:\n      interval: weekly\n"
        ),
        marker="only the uv ecosystem",
        where="template",
    ),
    Control(
        "dependabot-lockfile-only",
        "generated projects' Dependabot must leave the template-owned pyproject.toml floors alone",
        "python3 scripts/check_pins.py --root .",
        lambda p: edit(template_bot(p), "    versioning-strategy: lockfile-only\n", ""),
        marker="lockfile-only",
        where="template",
    ),
    Control(
        "gitleaks-version-agreement",
        "the gitleaks hook and copier.yml's gitleaks_version must name the same release",
        "python3 scripts/check_pins.py --root .",
        lambda p: edit(
            p / "copier.yml",
            "gitleaks_version:\n  type: str\n  default: "
            + re.search(r"gitleaks_version:\n  type: str\n  default: (\S+)", (p / "copier.yml").read_text()).group(1),
            "gitleaks_version:\n  type: str\n  default: 0.0.1",
        ),
        marker="gitleaks hook frozen tag",
        where="template",
    ),
    Control(
        "release-gate",
        "the release check passes at the current template_ref and refuses a sha256:PENDING digest",
        "python3 scripts/check_pins.py --root . --release"
        " --tag \"$(sed -n '/^template_ref:/,/^  default:/s/^  default: //p' copier.yml)\"",
        lambda p: (p / "copier.yml").write_text(
            re.sub(
                r"^(uv_image_digest:\n  type: str\n  default: )sha256:[0-9a-f]{64}$",
                r"\g<1>sha256:PENDING",
                (p / "copier.yml").read_text(),
                count=1,
                flags=re.MULTILINE,
            )
        ),
        marker="sha256:PENDING digests",
        where="template",
    ),
    Control(
        "dependency-updates-off",
        "dependency_updates=false renders no Dependabot config",
        'python3 scripts/render.py service-py313 --no-gates --out "$(mktemp -d)/x"',
        lambda p: template_bot(p).rename(template_bot(p).with_name("dependabot.yml.jinja")),
        marker="rendered although dependency_updates is false",
        where="template",
    ),
    Control(
        "workflow-scan",
        "an attacker-controllable expression in a workflow `run:` fails the zizmor hook",
        "uv run pre-commit run zizmor --all-files",
        lambda p: append(p / ".github/workflows/ci.yml", UNSAFE_JOB),
        marker="template-injection",
    ),
    Control(
        "workflow-scan-pin-scope",
        "only the template's own shared workflows may be called by tag; any other owner's must be SHA-pinned",
        "uv run pre-commit run zizmor --all-files",
        lambda p: edit(
            p / ".github/workflows/ci.yml",
            "uses: lloydbrian/python-project-template/",
            "uses: someone-else/python-project-template/",
        ),
        marker="unpinned-uses",
    ),
]


def sh(cmd: str, cwd: Path) -> tuple[int, str]:
    env = dict(os.environ)
    env.pop("VIRTUAL_ENV", None)
    # No .pyc files: a mutation and its restore can land in the same second with the same file
    # size, and Python would then reuse the mutated bytecode (pyc staleness is mtime + size).
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(cmd, shell=True, cwd=cwd, env=env, capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


def restore(where: Path) -> None:
    # reset --hard to the pristine commit also undoes controls that commit (secret-detection)
    subprocess.run(
        "git reset -q --hard pristine && git clean -fdq"
        " && find . -path ./.venv -prune -o -name __pycache__ -type d -exec rm -rf {} +",
        shell=True,
        cwd=where,
        check=True,
    )
    _rc, out = sh("git status --porcelain", where)
    if out.strip():
        raise SystemExit(f"restore failed in {where}:\n{out}")


def prepare(work: Path) -> tuple[Path, Path]:
    render = work / "render"
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/render.py"), "service", "--no-gates", "--out", str(render)],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    env_py = "3.15"
    for cmd in (
        "git init -q && git add -A && git -c user.name=nc -c user.email=nc@example.invalid commit -qm render",
        f"UV_PYTHON={env_py} uv lock -q && UV_PYTHON={env_py} uv sync -q --locked",
        "git add -A && git -c user.name=nc -c user.email=nc@example.invalid commit -qm lock && git tag pristine",
    ):
        subprocess.run(cmd, shell=True, cwd=render, check=True)
    template = work / "template-copy"
    shutil.copytree(ROOT, template, ignore=shutil.ignore_patterns(".git", ".render", ".venv", "__pycache__"))
    subprocess.run(
        "git init -q && git add -A && git -c user.name=nc -c user.email=nc@example.invalid commit -qm copy"
        " && git tag pristine",
        shell=True,
        cwd=template,
        check=True,
    )
    return render, template


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--only", nargs="*")
    args = parser.parse_args()
    controls = [c for c in CONTROLS if (not args.only or c.name in args.only) and not (args.offline and c.network)]
    if args.list:
        for c in CONTROLS:
            print(f"{c.name:30} {c.rule}{'  [network]' if c.network else ''}")
        return
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="negctl-") as tmp:
        render, template = prepare(Path(tmp))
        for c in controls:
            where = render if c.where == "render" else template
            rc0, out0 = sh(c.check, where)
            if rc0 != 0:
                failures.append(f"{c.name}: pristine check did not pass:\n{out0[-800:]}")
                print(f"FAIL  {c.name:30} (pristine did not pass)")
                continue
            c.mutate(where)
            rc1, out1 = sh(c.check, where)
            caught = rc1 != 0 and (c.marker in out1)
            restore(where)
            if c.network:
                sh("uv sync -q --locked", where)
            rc2, _out2 = sh(c.check, where)
            if caught and rc2 == 0:
                print(f"PASS  {c.name:30} broke it -> failed with '{c.marker or 'non-zero exit'}'; restored -> passes")
            else:
                why = "mutation was NOT caught" if not caught else "restored tree does not pass"
                failures.append(f"{c.name}: {why} (rc={rc1})\n{out1[-800:]}")
                print(f"FAIL  {c.name:30} {why}")
    skipped = len(CONTROLS) - len(controls)
    print(
        f"\nnegative controls: {len(controls) - len(failures)}/{len(controls)} caught"
        + (f", {skipped} skipped" if skipped else "")
    )
    if failures:
        print("\n" + "\n\n".join(failures))
        sys.exit(1)


if __name__ == "__main__":
    main()
