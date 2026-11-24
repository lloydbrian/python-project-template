#!/usr/bin/env python3
"""Enforce the supply-chain pin policy (ADR 0007). Standard library only.

    python3 scripts/check_pins.py                          # everyday check (CI lint job)
    python3 scripts/check_pins.py --release --tag v2.0.0   # release gate: also no PENDING digests

Rules:
  1. Every third-party `uses:` in .github/workflows is pinned to a 40-character commit SHA.
  2. Container images in template Containerfiles are fully qualified and never `:latest`.
  3. Versions agree: copier.yml's uv_version equals the uv-pre-commit rev in the template hooks,
     and the default mise-version in the shared workflows equals copier.yml's mise_version.
  4. (--release) template_ref equals the tag, and no digest is still sha256:PENDING.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SHA = re.compile(r"^[0-9a-f]{40}$")


def copier_value(text: str, key: str) -> str:
    match = re.search(rf"^{key}:\n(?:  .*\n)*?  default: (.+)$", text, re.MULTILINE)
    if not match:
        raise SystemExit(f"check_pins: cannot find {key} in copier.yml")
    return match.group(1).strip().strip('"')


def check(root: Path, release: bool, tag: str | None) -> list[str]:
    errors: list[str] = []
    for wf in sorted((root / ".github/workflows").glob("*.y*ml")):
        for n, line in enumerate(wf.read_text().splitlines(), 1):
            m = re.match(r"\s*-?\s*uses:\s*([^\s#]+)", line)
            if not m or m.group(1).startswith("./"):
                continue
            ref = m.group(1).rpartition("@")[2]
            if not SHA.match(ref):
                errors.append(f"{wf.relative_to(root)}:{n}: action not pinned to a commit SHA: {m.group(1)}")

    for cf in sorted((root / "template").rglob("Containerfile*")):
        for n, raw in enumerate(cf.read_text().splitlines(), 1):
            # Remove Jinja first: `{% if ... %}` contains spaces that would cut the image token short.
            line = re.sub(r"\{\{.*?\}\}", "X", re.sub(r"\{%.*?%\}", "", raw))
            m = re.match(r"\s*(?:FROM|COPY\s+--from=)\s*(\S+)", line, re.IGNORECASE)
            if not m:
                continue
            image = m.group(1)
            if "/" not in image and ":" not in image:
                continue  # a stage name such as `FROM build AS dev`
            name = image.split("@")[0]
            if name.endswith(":latest") or ":" not in name.rsplit("/", 1)[-1]:
                errors.append(f"{cf.relative_to(root)}:{n}: image must have an explicit version tag: {image}")
            if "/" not in name.split(":")[0] or "." not in name.split("/")[0]:
                errors.append(f"{cf.relative_to(root)}:{n}: image must be fully qualified (registry/...): {image}")

    copier = (root / "copier.yml").read_text()
    uv_version = copier_value(copier, "uv_version")
    hooks = (root / "template/.pre-commit-config.yaml.jinja").read_text()
    m = re.search(r"astral-sh/uv-pre-commit\n\s+rev:\s*(\S+)", hooks)
    if not m or m.group(1) != uv_version:
        errors.append(f"uv-pre-commit rev ({m.group(1) if m else 'missing'}) != copier uv_version ({uv_version})")
    mise_version = copier_value(copier, "mise_version")
    for wf in ("python-ci.yml", "python-release.yml"):
        text = (root / ".github/workflows" / wf).read_text()
        m = re.search(r"mise-version:\n(?:\s+.*\n)*?\s+default:\s*\"?([^\"\n]+)", text)
        if not m or m.group(1) != mise_version:
            errors.append(
                f"{wf} default mise-version ({m.group(1) if m else 'missing'}) != copier mise_version ({mise_version})"
            )

    if release:
        ref = copier_value(copier, "template_ref")
        if tag and ref != tag:
            errors.append(f"copier.yml template_ref is {ref} but the tag is {tag}: bump template_ref first")
        live = "\n".join(ln for ln in copier.splitlines() if not ln.lstrip().startswith("#"))
        if "sha256:PENDING" in live:
            errors.append("copier.yml still has sha256:PENDING digests: run `mise run pin-images` first")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--release", action="store_true")
    parser.add_argument("--tag")
    args = parser.parse_args()
    errors = check(args.root, args.release, args.tag)
    for e in errors:
        print(f"FAIL {e}")
    if errors:
        sys.exit(1)
    print("check_pins: OK" + (" (release)" if args.release else ""))


if __name__ == "__main__":
    main()
