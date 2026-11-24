#!/usr/bin/env python3
"""Prove `copier update` works the way the README promises.

Builds two throw-away template releases from the current working tree, generates a project at
the first, makes a local edit, then updates to the second and checks that:
  * the template change arrived (a new line in .env.example),
  * the local edit survived (README.md),
  * computed values moved forward without being asked (ci.yml now calls the new template_ref),
  * .copier-answers.yml records the new release and stores no computed values,
  * no conflicts or *.rej files were left.

    python3 scripts/update_test.py
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COPIER = os.environ.get("COPIER", "uvx --from copier==9.19.1 copier")
GIT = "git -c user.name=update-test -c user.email=update-test@example.invalid"
R1, R2 = "v9.0.0-rc.1", "v9.0.0-rc.2"  # tags must be PEP 440 versions or copier cannot order them
MARKER = "# update-test: this line arrived through copier update"


def sh(cmd: str, cwd: Path) -> str:
    env = dict(os.environ)
    env.pop("VIRTUAL_ENV", None)
    proc = subprocess.run(cmd, shell=True, cwd=cwd, env=env, capture_output=True, text=True)
    if proc.returncode:
        sys.exit(f"update-test: `{cmd}` failed:\n{proc.stdout}{proc.stderr}")
    return proc.stdout


def set_ref(tpl: Path, ref: str) -> None:
    path = tpl / "copier.yml"
    text, n = re.subn(r"(template_ref:\n(?:  .*\n)*?  default: )\S+", rf"\g<1>{ref}", path.read_text())
    if n != 1:
        sys.exit("update-test: template_ref not found in copier.yml")
    path.write_text(text)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="update-test-") as tmp:
        tpl, proj = Path(tmp) / "tpl", Path(tmp) / "proj"
        files = sh("git ls-files -z -co --exclude-standard", ROOT).split("\0")
        for rel in filter(None, files):
            src = ROOT / rel
            if src.is_file() and not rel.startswith(".render/"):
                (tpl / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, tpl / rel)
        sh("git init -q", tpl)
        set_ref(tpl, R1)
        sh(f"{GIT} add -A && {GIT} commit -qm r1 && git tag {R1}", tpl)

        sh(
            f"{COPIER} copy --defaults --quiet --vcs-ref {R1} --data 'project_name=Update Check' "
            f"{shlex.quote(str(tpl))} {shlex.quote(str(proj))}",
            Path(tmp),
        )
        with (proj / "README.md").open("a") as fh:
            fh.write("\n## Local notes\n\nThis section was written in the project and must survive updates.\n")
        sh(f"git init -q && {GIT} add -A && {GIT} commit -qm 'project at r1 + local edit'", proj)

        set_ref(tpl, R2)
        env_tpl = tpl / "template/.env.example.jinja"
        env_tpl.write_text(env_tpl.read_text() + MARKER + "\n")
        sh(f"{GIT} add -A && {GIT} commit -qm r2 && git tag {R2}", tpl)

        sh(f"{COPIER} update --defaults --quiet --vcs-ref {R2}", proj)

        answers = (proj / ".copier-answers.yml").read_text()
        checks = {
            "template change arrived": MARKER in (proj / ".env.example").read_text(),
            "local edit survived": "## Local notes" in (proj / "README.md").read_text(),
            "computed template_ref moved forward": f"python-ci.yml@{R2}"
            in (proj / ".github/workflows/ci.yml").read_text(),
            "answers record the new release": f"_commit: {R2}" in answers,
            "computed values are not stored as answers": "template_ref" not in answers
            and "has_container" not in answers,
            "no conflicts or .rej files": not list(proj.rglob("*.rej")) and "<<<<<<<" not in sh("git diff", proj),
        }
    failed = [name for name, ok in checks.items() if not ok]
    for name, ok in checks.items():
        print(f"{'PASS' if ok else 'FAIL'}  {name}")
    if failed:
        sys.exit(1)
    print(f"update-test: {R1} -> {R2} PASS")


if __name__ == "__main__":
    main()
