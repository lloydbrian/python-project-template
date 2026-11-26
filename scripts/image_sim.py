#!/usr/bin/env python3
"""Simulate a Containerfile's Python build stages without a container engine.

    python3 scripts/image_sim.py <rendered-project> [--target test]

Follows the stage chain up to the target (by default `test`: python-base -> build -> test),
copies into an empty folder ONLY what the stages' `COPY <src> <dst>` lines copy (minus anything
`.containerignore` excludes, as Podman would), checks that every `license-files` entry in
pyproject.toml was copied, and runs the
stages' `RUN` commands there (uv sync, pytest), skipping OS-level steps (apt-get, useradd,
chown, chmod). It catches build-context mistakes: a file the tests or the package build need
but the Containerfile never copies. It also checks that the OS-upgrade layer can be refreshed:
the first stage declares `ARG OS_REFRESH` before its `apt-get upgrade`, and `mise run image`
passes `--build-arg OS_REFRESH=...` (a digest-pinned base never invalidates that cached layer by
itself). It does not replace a real `podman build`.
Standard library only.
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

OS_STEPS = ("apt-get", "rm -rf /var/lib/apt", "useradd", "chown", "chmod", "python -m pip uninstall")


def stages(text: str) -> dict[str, tuple[str, list[tuple[str, str]]]]:
    """Return {stage: (parent, [(instruction, args), ...])}."""
    text = re.sub(r"\\\n", " ", text)
    out: dict[str, tuple[str, list[tuple[str, str]]]] = {}
    current = None
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        word, _, rest = line.partition(" ")
        word = word.upper()
        if word == "FROM":
            m = re.match(r"(\S+)\s+AS\s+(\S+)", rest, re.IGNORECASE)
            if not m:
                raise SystemExit(f"image_sim: unnamed stage: {line}")
            current = m.group(2)
            out[current] = (m.group(1), [])
        elif current:
            out[current][1].append((word, rest))
    return out


def ignore_rules(project: Path) -> list[tuple[bool, str]]:
    path = project / ".containerignore"
    rules = []
    for raw in path.read_text().splitlines() if path.exists() else []:
        line = raw.strip()
        if line and not line.startswith("#"):
            rules.append((line.startswith("!"), line.lstrip("!").rstrip("/")))
    return rules


def excluded(rel: str, rules: list[tuple[bool, str]]) -> bool:
    """Approximate .containerignore semantics: last matching rule wins; `**/x` matches at any depth."""
    out = False
    parts = rel.split("/")
    for negate, pat in rules:
        bare = pat[3:] if pat.startswith("**/") else pat
        prefixes = ["/".join(parts[: i + 1]) for i in range(len(parts))]
        hit = any(fnmatch.fnmatch(p, pat) for p in prefixes) or (
            pat.startswith("**/") and any(fnmatch.fnmatch(part, bare) for part in parts)
        )
        if hit:
            out = not negate
    return out


def chain(all_stages: dict[str, tuple[str, list[tuple[str, str]]]], target: str) -> list[str]:
    order = []
    while target in all_stages:
        order.insert(0, target)
        target = all_stages[target][0]
    return order


def check_os_refresh(project: Path, all_stages: dict[str, tuple[str, list[tuple[str, str]]]], first: str) -> None:
    """The cached `apt-get upgrade` layer must be re-runnable: ARG OS_REFRESH before it, passed by `mise run image`."""
    steps = all_stages[first][1]
    upgrade = next((i for i, (word, rest) in enumerate(steps) if word == "RUN" and "apt-get upgrade" in rest), None)
    if upgrade is None:
        return
    args = [i for i, (word, rest) in enumerate(steps) if word == "ARG" and rest.split("=")[0].strip() == "OS_REFRESH"]
    if not args or args[0] > upgrade:
        sys.exit(
            f"image_sim: [{first}] no `ARG OS_REFRESH` before `apt-get upgrade`: "
            "a cached upgrade layer would never refresh"
        )
    mise = (project / ".mise.toml").read_text()
    task = re.search(r"^\[tasks\.image\]\n(.*?)(?=^\[|\Z)", mise, re.MULTILINE | re.DOTALL)
    if not task or "--build-arg OS_REFRESH=" not in task.group(1):
        sys.exit(
            "image_sim: `mise run image` does not pass --build-arg OS_REFRESH=...: "
            "the OS-upgrade layer would never refresh"
        )
    print(f"image_sim: [{first}] OS_REFRESH declared before apt-get upgrade and passed by `mise run image`")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("project", type=Path)
    parser.add_argument("--target", default="test")
    args = parser.parse_args()
    project = args.project.resolve()
    all_stages = stages((project / ".container/Containerfile").read_text())
    order = chain(all_stages, args.target)
    if not order or order[-1] != args.target:
        raise SystemExit(f"image_sim: no stage named {args.target}")
    check_os_refresh(project, all_stages, order[0])
    rules = ignore_rules(project)
    python = re.search(r'^python\s*=\s*"([^"]+)"', (project / ".mise.toml").read_text(), re.MULTILINE)
    with tempfile.TemporaryDirectory(prefix="image-sim-") as tmp:
        app, venv = Path(tmp) / "app", Path(tmp) / "venv"
        app.mkdir()
        env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
        env.update(UV_PROJECT_ENVIRONMENT=str(venv), UV_NO_CACHE="1", PATH=f"{venv}/bin:{env['PATH']}")
        if python:
            env["UV_PYTHON"] = python.group(1)
        print(f"image_sim: stages {' -> '.join(order)} (copying only what COPY lines copy)")
        for name in order:
            for word, rest in all_stages[name][1]:
                if word == "COPY" and "--from=" not in rest:
                    *srcs, _dst = [a for a in shlex.split(rest) if not a.startswith("--")]
                    for src in srcs:
                        source = project / src
                        if not source.exists():
                            sys.exit(f"image_sim: [{name}] COPY source missing in project: {src}")
                        if excluded(src, rules):
                            continue  # Podman never sends it: it is in .containerignore
                        dest = app / src
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        if source.is_dir():
                            shutil.copytree(
                                source,
                                dest,
                                ignore=lambda d, names, s=src, root=source: [
                                    n for n in names if excluded(str(Path(s, Path(d).relative_to(root), n)), rules)
                                ],
                            )
                        else:
                            shutil.copy2(source, dest)
                    if "pyproject.toml" in srcs:
                        files = re.search(r"^license-files\s*=\s*\[(.*?)\]", (app / "pyproject.toml").read_text(), re.M)
                        for lic in re.findall(r'"([^"]+)"', files.group(1)) if files else []:
                            if not list(app.glob(lic)):
                                sys.exit(
                                    f"image_sim: [{name}] pyproject license-files {lic!r} is not in the build context"
                                )
                elif word == "RUN":
                    for step in (s.strip() for s in rest.split("&&")):
                        if not step or step.startswith(OS_STEPS):
                            continue
                        print(f"  [{name}] $ {step}", flush=True)
                        proc = subprocess.run(step, shell=True, cwd=app, env=env, capture_output=True, text=True)
                        if proc.returncode:
                            sys.exit(f"image_sim: [{name}] `{step}` failed:\n{(proc.stdout + proc.stderr)[-2000:]}")
    print(f"image_sim: target {args.target}: PASS")


if __name__ == "__main__":
    main()
