#!/usr/bin/env python3
"""Dry-run the release build path of python-release.yml on a rendered service, without a tag.

    mise run release-dry-run -- arm64        # on an arm64 machine or runner
    mise run release-dry-run -- amd64        # on an amd64 machine or runner

Why: template CI renders and gates every variant, but the release workflow only ever ran on a
real tag. rc.3's bug (trivy cannot read an OCI archive file with --input) was found by a
downstream test release. This runs the same steps in the template PR.

What it does:
  1. Renders the service variant (scripts/render.py), commits it, runs `mise run bootstrap` and
     commits the lockfile, as a new project would before its first release.
  2. Reads the generated project's .github/workflows/release.yml for the inputs it passes
     (name, target) and .github/workflows/python-release.yml from THIS repo for the steps.
  3. Runs every `run:` step of the `build` job in order with `bash -eo pipefail`, as GitHub does:
     the tag/version check (with the synthetic tag v<version>), `mise run ci`, the native image
     build, the OCI archive export, the unpack, the scan and the SBOM. GITHUB_ENV and GITHUB_OUTPUT
     are emulated between steps. Each step runs under `mise exec` in the project, so it sees the
     project's pinned tools, as it does after the workflow's mise-action step. `uses:` steps are
     skipped: actionlint and the pin policy cover them.
  4. Checks dist/ holds exactly this arch's OCI archive and SBOM, that both match the `attest`
     job's subject-path globs, and that the SBOM is CycloneDX JSON.

It refuses any `${{ }}` expression, step key or job env value it cannot emulate, so a later edit to
the workflow cannot silently escape the dry run. Not covered: `attest` and `publish` (they need a
real tag, id-token and contents: write). Needs PyYAML (the mise task provides a pinned one).
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import render  # noqa: E402  (scripts/render.py: the same render the template CI uses)

WORKFLOW = ROOT / ".github/workflows/python-release.yml"
STEP_KEYS = {"name", "id", "run", "uses", "with"}
HOST_ARCH = {"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64"}


def sh(cmd: str, cwd: Path, env: dict[str, str]) -> None:
    print(f"  $ {cmd}", flush=True)
    subprocess.run(cmd, shell=True, cwd=cwd, env=env, check=True)


def resolve(value: str, known: dict[str, str], where: str) -> str:
    def sub(m: re.Match[str]) -> str:
        expr = m.group(1).strip()
        if expr not in known:
            sys.exit(f"release-dry-run: {where}: cannot emulate ${{{{ {expr} }}}}; teach the dry run or simplify")
        return known[expr]

    return re.sub(r"\$\{\{(.*?)\}\}", sub, value)


def read_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text().splitlines():
        if not line:
            continue
        if "<<" in line.split("=", 1)[0]:
            sys.exit(f"release-dry-run: multi-line GITHUB_ENV/GITHUB_OUTPUT values are not emulated: {line}")
        key, _, value = line.partition("=")
        out[key] = value
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--arch", choices=["amd64", "arm64"], required=True)
    parser.add_argument("--out", type=Path, help="work folder (default: <tmp>/python-project-template-release-dry-run)")
    args = parser.parse_args()
    host = HOST_ARCH.get(platform.machine().lower())
    if host != args.arch:
        sys.exit(f"release-dry-run: the release builds natively; this host is {platform.machine()}, not {args.arch}")

    work = (args.out or Path(tempfile.gettempdir()) / "python-project-template-release-dry-run").resolve()
    project, runner_temp = work / "project", work / "runner-temp"
    print(f"release-dry-run {args.arch} -> {work}")
    data = render.render("service", project)
    render.check_tree("service", data, project)
    runner_temp.mkdir(parents=True, exist_ok=True)

    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    env["MISE_TRUSTED_CONFIG_PATHS"] = f"{env.get('MISE_TRUSTED_CONFIG_PATHS', '')}:{project}".strip(":")
    git = "git -c user.name=release-dry-run -c user.email=release-dry-run@example.invalid"
    sh(f"git init -q && git add -A && {git} commit -qm 'chore: render'", project, env)
    sh("mise install && mise run bootstrap", project, env)
    sh(f"git add -A && {git} commit -qm 'chore: bootstrap (lockfile)'", project, env)
    if subprocess.run("git status --porcelain", shell=True, cwd=project, capture_output=True, text=True).stdout:
        sys.exit("release-dry-run: the bootstrapped project is not clean after committing")

    caller = yaml.safe_load((project / ".github/workflows/release.yml").read_text())
    with_ = caller["jobs"]["release"]["with"]
    wf = yaml.safe_load(WORKFLOW.read_text())
    inputs = wf.get(True, wf.get("on"))["workflow_call"]["inputs"]  # YAML 1.1 reads the key `on` as True
    name = str(with_["name"])
    target = str(with_.get("target", inputs["target"]["default"]))
    uv_version = ["mise", "exec", "--", "uv", "version", "--short"]
    version = subprocess.run(uv_version, cwd=project, env=env, capture_output=True, text=True, check=True).stdout
    version = version.strip()
    sha = subprocess.run("git rev-parse HEAD", shell=True, cwd=project, capture_output=True, text=True).stdout.strip()

    known = {
        "github.workspace": str(project),
        "inputs.name": name,
        "inputs.target": target,
        "matrix.arch": args.arch,
    }
    job = wf["jobs"]["build"]
    for key, value in job.get("env", {}).items():
        env[key] = resolve(str(value), known, f"build.env.{key}")
    env.update(
        GITHUB_REF_NAME=f"v{version}",
        GITHUB_SHA=sha,
        GITHUB_SERVER_URL="https://github.com",
        GITHUB_REPOSITORY=f"release-dry-run/{name}",
        GITHUB_WORKSPACE=str(project),
        RUNNER_TEMP=str(runner_temp),
    )

    ran = 0
    for i, step in enumerate(job["steps"], 1):
        label = step.get("name") or step.get("uses") or f"step {i}"
        extra = set(step) - STEP_KEYS
        if extra:
            sys.exit(f"release-dry-run: step {label!r} uses {sorted(extra)}, which the dry run does not emulate")
        if "run" not in step:
            print(f"- skip (uses): {label}")
            continue
        script = resolve(step["run"], known, f"step {label!r}")
        github_env, github_output = runner_temp / f"env-{i}", runner_temp / f"output-{i}"
        github_env.write_text("")
        github_output.write_text("")
        print(f"- run: {resolve(label, known, 'step name')}", flush=True)
        step_env = dict(env, GITHUB_ENV=str(github_env), GITHUB_OUTPUT=str(github_output))
        bash = ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", script]
        proc = subprocess.run(["mise", "exec", "--", *bash], cwd=project, env=step_env)
        if proc.returncode:
            sys.exit(f"release-dry-run: step {label!r} failed (exit {proc.returncode})")
        env.update(read_env_file(github_env))
        read_env_file(github_output)  # parsed for format errors only
        ran += 1

    dist = project / "dist"
    files = sorted(p.name for p in dist.iterdir()) if dist.is_dir() else []
    want = sorted([f"{name}-{version}-linux-{args.arch}.oci.tar", f"{name}-{version}-linux-{args.arch}.sbom.cdx.json"])
    if files != want:
        sys.exit(f"release-dry-run: dist/ holds {files}, expected {want}")
    attest = next(s for s in wf["jobs"]["attest"]["steps"] if "subject-path" in s.get("with", {}))
    globs = [g.strip() for g in attest["with"]["subject-path"].splitlines() if g.strip()]
    for f in files:
        if not any(fnmatch.fnmatch(f"dist/{f}", g) for g in globs):
            sys.exit(f"release-dry-run: dist/{f} matches none of the attest subject-path globs {globs}")
    sbom = json.loads((dist / want[1]).read_text())
    if sbom.get("bomFormat") != "CycloneDX" or not sbom.get("components"):
        sys.exit("release-dry-run: the SBOM is not a CycloneDX document with components")
    print(f"release-dry-run {args.arch}: PASS ({ran} run steps of the python-release.yml build job; dist/ = {files})")


if __name__ == "__main__":
    main()
