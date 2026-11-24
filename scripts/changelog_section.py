#!/usr/bin/env python3
"""Print one version's section of CHANGELOG.md (used for GitHub release notes).

    python3 scripts/changelog_section.py 2.0.0
A pre-release such as 2.0.0-rc.1 falls back to the 2.0.0 section.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

version = sys.argv[1]
text = (Path(__file__).resolve().parent.parent / "CHANGELOG.md").read_text()
for candidate in (version, version.split("-")[0]):
    m = re.search(rf"^## \[{re.escape(candidate)}\].*?$(.*?)(?=^## \[|\Z)", text, re.MULTILINE | re.DOTALL)
    if m:
        print(m.group(1).strip())
        break
else:
    sys.exit(f"CHANGELOG.md has no section for {version}")
