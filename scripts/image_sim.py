#!/usr/bin/env python3
"""Simulate a Containerfile's Python build stages without a container engine.

    python3 scripts/image_sim.py <rendered-project> [--target test]

Follows the stage chain up to the target (by default `test`: python-base -> build -> test),
copies into an empty folder ONLY what the stages' `COPY <src> <dst>` lines copy, and runs the
stages' `RUN` commands there (uv sync, pytest), skipping OS-level steps (apt-get, useradd,
chown, chmod). It catches build-context mistakes: a file the tests or the package build need
but the Containerfile never copies. It does not replace a real `podman build`.
Standard library only.
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


def chain(all_stages: dict[str, tuple[str, list[tuple[str, str]]]], target: str) -> list[str]:
    order = []
    while target in all_stages:
        order.insert(0, target)
        target = all_stages[target][0]
    return order


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
                if word == "COPY" and not rest.startswith("--"):
                    *srcs, _dst = shlex.split(rest)
                    for src in srcs:
                        source = project / src
                        if not source.exists():
                            sys.exit(f"image_sim: [{name}] COPY source missing in project: {src}")
                        dest = app / src
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        (shutil.copytree if source.is_dir() else shutil.copy2)(source, dest)
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
