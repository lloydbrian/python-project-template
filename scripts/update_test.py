#!/usr/bin/env python3
"""Prove `copier update` works the way the README promises.

Builds two throw-away template releases from the current working tree, generates a project at
the first, makes a local edit, then updates to the second and checks that:
  * the template change arrived (a new line in .env.example),
  * the local edit survived (README.md),
  * computed values moved forward without being asked (ci.yml now calls the new template_ref),
  * .copier-answers.yml records the new release and stores no computed values,
  * no conflicts or *.rej files were left,
  * a question added after the project was generated (dependency_updates; the first release
    is built without it) takes its default, so Dependabot arrives with the update,
  * answering it false later, with the README's command (which stays on the project's current
    template tag), removes the file without conflicts.

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


def drop_new_question(tpl: Path) -> None:
    # The first throw-away release predates the dependency_updates question (as v2.0.1 does).
    path = tpl / "copier.yml"
    text, n = re.subn(r"\ndependency_updates:\n(?:  .*\n)+", "\n", path.read_text())
    if n != 1:
        sys.exit("update-test: dependency_updates question not found in copier.yml")
    path.write_text(text)
    bots = list((tpl / "template/.github").glob("*dependabot.yml*.jinja"))
    if len(bots) != 1:
        sys.exit("update-test: template Dependabot config not found")
    bots[0].unlink()


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
        drop_new_question(tpl)
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

        github = sh("git ls-files -z -co --exclude-standard template/.github", ROOT).split("\0")
        for rel in ("copier.yml", *filter(None, github)):  # names contain spaces: split on NUL
            if (ROOT / rel).is_file():  # a tracked file deleted but not yet staged is skipped, as above
                shutil.copy2(ROOT / rel, tpl / rel)  # R2 brings the question and its file back
        set_ref(tpl, R2)
        env_tpl = tpl / "template/.env.example.jinja"
        env_tpl.write_text(env_tpl.read_text() + MARKER + "\n")
        sh(f"{GIT} add -A && {GIT} commit -qm r2 && git tag {R2}", tpl)

        had_bot = (proj / ".github/dependabot.yml").exists()
        sh(f"{COPIER} update --defaults --quiet --vcs-ref {R2}", proj)

        answers = (proj / ".copier-answers.yml").read_text()
        bot_arrived = not had_bot and (proj / ".github/dependabot.yml").is_file()
        no_conflicts = not list(proj.rglob("*.rej")) and "<<<<<<<" not in sh("git diff", proj)
        sh(f"{GIT} add -A && {GIT} commit -qm 'update to r2'", proj)
        # The opt-out exactly as the generated README documents it (works on every supported Copier)
        current = "\"$(sed -n 's/^_commit: //p' .copier-answers.yml)\""
        sh(f"{COPIER} update --defaults --quiet --vcs-ref {current} --data dependency_updates=false", proj)
        opted_out = (proj / ".copier-answers.yml").read_text()
        opt_out_clean = not list(proj.rglob("*.rej")) and "<<<<<<<" not in sh("git diff", proj)
        checks = {
            "template change arrived": MARKER in (proj / ".env.example").read_text(),
            "local edit survived": "## Local notes" in (proj / "README.md").read_text(),
            "computed template_ref moved forward": f"python-ci.yml@{R2}"
            in (proj / ".github/workflows/ci.yml").read_text(),
            "answers record the new release": f"_commit: {R2}" in answers,
            "computed values are not stored as answers": "template_ref" not in answers
            and "has_container" not in answers,
            "no conflicts or .rej files": no_conflicts,
            "new question took its default (dependency_updates: true)": "dependency_updates: true" in answers,
            "Dependabot arrived with the update": bot_arrived,
            "answering dependency_updates=false removes it, on the same release, without conflicts": (
                "dependency_updates: false" in opted_out
                and f"_commit: {R2}" in opted_out
                and not (proj / ".github/dependabot.yml").exists()
                and opt_out_clean
            ),
        }
    failed = [name for name, ok in checks.items() if not ok]
    for name, ok in checks.items():
        print(f"{'PASS' if ok else 'FAIL'}  {name}")
    if failed:
        sys.exit(1)
    print(f"update-test: {R1} -> {R2} PASS")


if __name__ == "__main__":
    main()
