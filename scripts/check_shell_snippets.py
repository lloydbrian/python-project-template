#!/usr/bin/env python3
"""Reject shell commands in docs that an interactive zsh or bash would mangle.

Interactive shells history-expand "!" outside single quotes: `git commit -m "feat!: x"` fails in
zsh with "illegal modifier" (and recalls history in bash). Developers paste commands from these
READMEs and runbooks, so every fenced bash/sh/zsh/shell block in *.md and *.md.jinja is checked.
Safe forms: single quotes ('feat!: x'), or "!" followed by a space, "=" or "(" (as in `[ ! -e x ]`).

    python3 scripts/check_shell_snippets.py            # all tracked docs
    python3 scripts/check_shell_snippets.py FILE...    # specific files
Standard library only.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

BLOCK = re.compile(r"```(?:bash|sh|zsh|shell|console)\n(.*?)```", re.S)
SINGLE_QUOTED = re.compile(r"'[^']*'")
COMMENT = re.compile(r"(^|\s)#.*$")
RISKY_BANG = re.compile(r"!(?=[^\s=(])")


def problems(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    found = []
    for block in BLOCK.finditer(text):
        first_line = text[: block.start()].count("\n") + 2
        for offset, line in enumerate(block.group(1).splitlines()):
            code = COMMENT.sub("", SINGLE_QUOTED.sub("''", line))
            if RISKY_BANG.search(code):
                found.append(f"{path}:{first_line + offset}: '!' would be history-expanded: {line.strip()}")
    return found


def main(argv: list[str]) -> int:
    files = [Path(a) for a in argv] or [
        Path(p)
        for p in subprocess.run(
            ["git", "ls-files", "-z", "*.md", "*.md.jinja"], capture_output=True, text=True, check=True
        ).stdout.split("\0")
        if p
    ]
    found = [f for path in files for f in problems(path)]
    for f in found:
        print(f)
    if found:
        print("Use single quotes around text containing '!' (for example 'feat!: ...').", file=sys.stderr)
        return 1
    print(f"check_shell_snippets: OK ({len(files)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
