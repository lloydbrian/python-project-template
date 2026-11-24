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
        "name-validator",
        "a project name that would break TOML/Python is refused at question time",
        "! ${COPIER:-uvx --from copier==9.19.1 copier} copy --defaults --quiet --vcs-ref HEAD"
        " --data 'project_name=a\"b' --data description=ok . $(mktemp -d)/x",
        lambda p: edit(p / "copier.yml", "{% elif '\"' in project_name", "{% elif false and '\"' in project_name"),
        marker="",
        where="template",
    ),
]


def sh(cmd: str, cwd: Path) -> tuple[int, str]:
    env = dict(os.environ)
    env.pop("VIRTUAL_ENV", None)
    proc = subprocess.run(cmd, shell=True, cwd=cwd, env=env, capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


def restore(where: Path) -> None:
    # reset --hard to the pristine commit also undoes controls that commit (secret-detection)
    subprocess.run("git reset -q --hard pristine && git clean -fdq", shell=True, cwd=where, check=True)
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
    env_py = "3.14"
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
