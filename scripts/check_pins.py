#!/usr/bin/env python3
"""Enforce the supply-chain pin policy (ADR 0007, ADR 0013). Standard library only.

    python3 scripts/check_pins.py                          # everyday check (CI lint job)
    python3 scripts/check_pins.py --release --tag v2.0.0   # release gate: also no PENDING digests

Rules:
  1. Every third-party `uses:` in .github/workflows is pinned to a 40-character commit SHA.
  2. Container images in template Containerfiles are fully qualified and never `:latest`.
  3. Every pre-commit hook `rev:` (template and this repo) is a 40-character commit SHA with the
     tag in a `# frozen: <tag>` comment.
  4. Versions agree: copier.yml's uv_version equals the uv-pre-commit frozen tag and its
     gitleaks_version equals the gitleaks hook's frozen tag (without the "v"); the shared
     workflows' default mise-version equals copier.yml's mise_version; and the root .mise.toml
     pins the same uv, trivy and gitleaks versions as copier.yml.
  5. (--release) template_ref equals the tag, and no digest is still sha256:PENDING.
  6. A hook repo in both this repo's .pre-commit-config.yaml and the template's uses the same rev
     and frozen tag: Dependabot bumps only the root file, so its PR fails here until the template
     copy matches.
  7. The template's Dependabot config (generated projects) lists only the uv ecosystem, with
     versioning-strategy lockfile-only: everything else a project pins, including the
     pyproject.toml floors, is owned by the template and arrives with copier update.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SHA = re.compile(r"^[0-9a-f]{40}$")


HOOK = re.compile(r"^\s*-\s*repo:\s*(\S+)\n\s+rev:\s*(\S+)(?:\s+#\s*frozen:\s*(\S+))?", re.MULTILINE)
ECOSYSTEM = re.compile(r"^\s*-?\s*package-ecosystem:\s*[\"']?([\w-]+)", re.MULTILINE)


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
    for cfg in (root / "template/.pre-commit-config.yaml.jinja", root / ".pre-commit-config.yaml"):
        for n, line in enumerate(cfg.read_text().splitlines(), 1):
            m = re.match(r"\s*rev:\s*(\S+)(?:\s+#\s*frozen:\s*(\S+))?", line)
            if m and not (SHA.match(m.group(1)) and m.group(2)):
                errors.append(f"{cfg.relative_to(root)}:{n}: hook rev must be a commit SHA with '# frozen: <tag>'")
    m = re.search(r"astral-sh/uv-pre-commit\n\s+rev:\s*\S+\s+#\s*frozen:\s*(\S+)", hooks)
    if not m or m.group(1) != uv_version:
        errors.append(
            f"uv-pre-commit frozen tag ({m.group(1) if m else 'missing'}) != copier uv_version ({uv_version})"
        )
    gitleaks_version = copier_value(copier, "gitleaks_version")
    m = re.search(r"gitleaks/gitleaks\n\s+rev:\s*\S+\s+#\s*frozen:\s*v?(\S+)", hooks)
    if not m or m.group(1) != gitleaks_version:
        errors.append(
            f"gitleaks hook frozen tag ({m.group(1) if m else 'missing'}) != copier gitleaks_version"
            f" ({gitleaks_version}): bump them together"
        )
    root_mise = (root / ".mise.toml").read_text()
    for tool, key in (("uv", "uv_version"), ("trivy", "trivy_version"), ("gitleaks", "gitleaks_version")):
        m = re.search(rf'^{tool}\s*=\s*"([^"]+)"', root_mise, re.MULTILINE)
        want = copier_value(copier, key)
        if not m or m.group(1) != want:
            errors.append(f"root .mise.toml {tool} ({m.group(1) if m else 'missing'}) != copier {key} ({want})")
    mise_version = copier_value(copier, "mise_version")
    for wf in ("python-ci.yml", "python-release.yml"):
        text = (root / ".github/workflows" / wf).read_text()
        m = re.search(r"mise-version:\n(?:\s+.*\n)*?\s+default:\s*\"?([^\"\n]+)", text)
        if not m or m.group(1) != mise_version:
            errors.append(
                f"{wf} default mise-version ({m.group(1) if m else 'missing'}) != copier mise_version ({mise_version})"
            )

    root_hooks = {repo: (rev, tag) for repo, rev, tag in HOOK.findall((root / ".pre-commit-config.yaml").read_text())}
    for repo, rev, frozen in HOOK.findall(hooks):  # not `tag`: that name is the --tag argument
        if repo in root_hooks and root_hooks[repo] != (rev, frozen):
            r_rev, r_tag = root_hooks[repo]
            errors.append(
                f"hook {repo}: .pre-commit-config.yaml has {r_rev[:12]} ({r_tag or 'no tag'}), which differs from the"
                f" template's {rev[:12]} ({frozen or 'no tag'}): give both configs the same rev and '# frozen:' tag"
            )
    bots = sorted((root / "template/.github").glob("*dependabot.yml*.jinja"))
    if len(bots) != 1:
        errors.append(f"expected one template Dependabot config in template/.github, found {len(bots)}")
    else:
        bot = bots[0].read_text()
        found = ECOSYSTEM.findall(bot)
        if found != ["uv"]:
            errors.append(
                f"{bots[0].relative_to(root)}: generated projects' Dependabot must list only the uv ecosystem,"
                f" found {found or 'none'} (ADR 0013)"
            )
        if not re.search(r"^\s+versioning-strategy:\s*lockfile-only\s*$", bot, re.MULTILINE):
            errors.append(
                f"{bots[0].relative_to(root)}: the uv updater must set 'versioning-strategy: lockfile-only'"
                " (the pyproject.toml floors belong to the template; ADR 0013)"
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
