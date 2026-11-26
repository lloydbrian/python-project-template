#!/usr/bin/env python3
"""Render one template variant and run its gates, exactly as a new project would.

    python3 scripts/render.py service                 # render (into <tmp>/...-render/service) and run its gates
    python3 scripts/render.py notebooks --no-gates    # render only
    REQUIRE_CONTAINER=1 python3 scripts/render.py service   # also build, scan and smoke-test the image

Runner: `--runner mise` (default, what CI uses) calls the rendered project's own mise tasks.
`--runner direct` runs the same commands without mise, for machines where mise cannot install
tools. Standard library only, so it runs before any project environment exists.
"""

from __future__ import annotations

import argparse
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COPIER = shlex.split(os.environ.get("COPIER", "uvx --from copier==9.19.1 copier"))

VARIANTS: dict[str, dict[str, object]] = {
    "service": {"project_name": "Ref Service", "project_type": "service"},
    "library": {"project_name": "Ref Library", "project_type": "library"},
    "library-container": {
        "project_name": "Ref Library Box",
        "project_type": "library",
        "include_container": True,
        "license": "MIT",  # exercises LICENSE in the image build context
    },
    "notebooks": {"project_name": "Ref Notebooks", "project_type": "notebooks"},
    # AI stacks: LanceDB on the default Python, ChromaDB on the newest Python it supports
    "service-ai-lancedb": {"project_name": "Ref AI Service", "project_type": "service", "ai_stack": "lancedb"},
    "notebooks-ai-chromadb": {
        "project_name": "Ref AI Notebooks",
        "project_type": "notebooks",
        "ai_stack": "chromadb",
        "python_version": "3.14",
    },
    "service-py314": {
        "project_name": "Ref Service 314",
        "project_type": "service",
        "python_version": "3.14",
    },
    "service-py313": {
        "project_name": "Ref Service 313",
        "project_type": "service",
        "python_version": "3.13",
    },
}

# Files every variant must have, and files that must exist only for some variants.
ALWAYS = [
    ".copier-answers.yml",
    ".env.example",
    ".gitignore",
    ".mise.toml",
    ".pre-commit-config.yaml",
    ".github/workflows/ci.yml",
    ".vscode/settings.json",
    "pyproject.toml",
    "README.md",
    "CHANGELOG.md",
    "docs/adr/README.md",
    "tests/__init__.py",
]
CONTAINER = [
    ".container/Containerfile",
    ".containerignore",
    ".trivyignore",
    "tools/check_scan_exceptions.py",
    "tests/test_scan_exceptions.py",
    ".github/workflows/release.yml",
]
UNRENDERED = re.compile(r"\{\{\s*[a-z_]+|\{%-?\s*(if|for|set|endif|raw)\b")


def run(cmd: list[str] | str, cwd: Path, env: dict[str, str] | None = None) -> None:
    shown = cmd if isinstance(cmd, str) else shlex.join(cmd)
    print(f"  $ {shown}", flush=True)
    subprocess.run(cmd, cwd=cwd, env=env, check=True, shell=isinstance(cmd, str))


def render(variant: str, out: Path) -> dict[str, object]:
    data = VARIANTS[variant]
    if out.exists():
        shutil.rmtree(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    args = [*COPIER, "copy", "--defaults", "--vcs-ref", "HEAD", "--quiet"]
    for key, value in data.items():
        args += ["--data", f"{key}={str(value).lower() if isinstance(value, bool) else value}"]
    run([*args, str(ROOT), str(out)], cwd=ROOT)
    return data


def check_tree(variant: str, data: dict[str, object], out: Path) -> None:
    ptype = data["project_type"]
    has_container = ptype in ("service", "notebooks") or bool(data.get("include_container"))
    expected = list(ALWAYS) + (CONTAINER if has_container else [])
    if data.get("license", "Proprietary") != "Proprietary":
        expected.append("LICENSE")
    if ptype != "library" and has_container:
        expected.append(".container/compose.yaml")
    if ptype == "notebooks":
        expected.append("notebooks/README.md")
    ai = data.get("ai_stack", "none")
    pkg = str(data["project_name"]).lower().replace(" ", "_")
    if ai != "none":
        expected += [f"src/{pkg}/rag.py", f"src/{pkg}/web_search.py", "tests/test_rag.py", "tests/test_web_search.py"]
    if ai == "chromadb":
        expected.append(".pip-audit-ignore")
    missing = [f for f in expected if not (out / f).is_file()]
    unexpected = [f for f in CONTAINER if not has_container and (out / f).exists()]
    leftovers = []
    for path in out.rglob("*"):
        if path.is_file() and ".git" not in path.parts:
            text = path.read_text(encoding="utf-8", errors="ignore")
            if UNRENDERED.search(text) and path.name != "README.md":
                leftovers.append(str(path.relative_to(out)))
            if "{{" in path.name or "{%" in path.name:
                leftovers.append(f"(file name) {path.relative_to(out)}")
    answers = (out / ".copier-answers.yml").read_text()
    problems = []
    if missing:
        problems.append(f"missing files: {missing}")
    if unexpected:
        problems.append(f"container files in a non-container variant: {unexpected}")
    if leftovers:
        problems.append(f"unrendered template syntax: {leftovers}")
    if "_commit:" not in answers or "_src_path:" not in answers:
        problems.append(".copier-answers.yml lacks _commit/_src_path (copier update would not work)")
    if problems:
        sys.exit(f"render-test {variant}: " + "; ".join(problems))
    print(f"  tree OK: {len(expected)} required files present, no unrendered syntax")


def gates(data: dict[str, object], out: Path, runner: str) -> None:
    env = dict(os.environ)
    env.pop("VIRTUAL_ENV", None)
    ptype = data["project_type"]
    has_container = (out / ".container/Containerfile").is_file()
    run(
        "git init -q && git add -A && git -c user.name=render -c user.email=render@example.invalid "
        "commit -qm 'chore: render'",
        cwd=out,
    )
    if runner == "mise":
        env["MISE_TRUSTED_CONFIG_PATHS"] = f"{env.get('MISE_TRUSTED_CONFIG_PATHS', '')}:{out}".strip(":")
        for task in ("install", "run bootstrap", "run ci", "run security"):
            run(f"mise {task}", cwd=out, env=env)
    else:
        env["UV_PYTHON"] = str(data.get("python_version", "3.15"))
        group = " --group notebooks" if ptype == "notebooks" else ""
        exceptions = "uv run python tools/check_scan_exceptions.py"
        audit = (
            [
                f"{exceptions} --stamp .pip-audit-ignore",
                f"{exceptions} .pip-audit-ignore",
                f"uv run --group security pip-audit $({exceptions} --pip-audit-args .pip-audit-ignore)",
            ]
            if has_container
            else ["uv run --group security pip-audit"]
        )
        for cmd in (
            "uv lock -q",
            f"uv sync -q --locked{group}",
            "uv run pre-commit run --all-files",
            "uv run mypy",
            'uv run pytest -q -m "not live"',
            *audit,
            "uv run --group security bandit -q -r src",
            "gitleaks git --redact --no-banner .",
        ):
            run(cmd, cwd=out, env=env)
    if not has_container:
        return
    # Build-context check without a container engine: catches files the image needs but never copies.
    run([sys.executable, str(ROOT / "scripts/image_sim.py"), str(out)], cwd=ROOT, env=env)
    if os.environ.get("REQUIRE_CONTAINER") != "1":
        print("  container stages skipped (set REQUIRE_CONTAINER=1 to build, scan and smoke-test)")
        return
    run(
        'podman build --build-arg OS_REFRESH="$(date -u +%F)" -f .container/Containerfile --target test .',
        cwd=out,
        env=env,
    )
    for task in ("image", "scan", "sbom") + (("smoke",) if ptype == "service" else ()):
        run(f"mise run {task}", cwd=out, env=env)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("variant", choices=sorted(VARIANTS))
    parser.add_argument(
        "--out", type=Path, help="output folder (default: <tmp>/python-project-template-render/<variant>)"
    )
    parser.add_argument("--no-gates", action="store_true", help="render and check the tree only")
    parser.add_argument("--runner", choices=["mise", "direct"], default="mise")
    args = parser.parse_args()
    # Outside this repo on purpose: mise would otherwise merge the root .mise.toml into the
    # rendered project, and the test would not prove the generated .mise.toml stands alone.
    default = Path(tempfile.gettempdir()) / "python-project-template-render" / args.variant
    out = (args.out or default).resolve()
    print(f"render-test {args.variant} -> {out}")
    data = render(args.variant, out)
    check_tree(args.variant, data, out)
    if not args.no_gates:
        gates(data, out, args.runner)
    print(f"render-test {args.variant}: PASS")


if __name__ == "__main__":
    main()
