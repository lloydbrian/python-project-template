#!/usr/bin/env bash
# pin_images.sh — resolve the multi-arch index digests of the base images and pin them in copier.yml.
#
#   mise run pin-images              # DRY RUN: prints the digests and the copier.yml change
#   mise run pin-images -- --write   # apply the change to copier.yml (review with `git diff`)
#
# Run by the template maintainer before a release, on a machine that can reach the registries.
# Needs `skopeo` (brew install skopeo). Reads registries only; writes nothing except copier.yml,
# and only with --write.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WRITE=0
[ "${1:-}" = "--write" ] && WRITE=1

uv_version="$(awk '/^uv_version:/{f=1} f&&/default:/{print $2; exit}' "$ROOT/copier.yml")"
[ -n "$uv_version" ] || { echo "cannot read uv_version from copier.yml" >&2; exit 1; }

command -v skopeo >/dev/null 2>&1 || { echo "skopeo is required: brew install skopeo" >&2; exit 1; }

digest_of() {   # $1 = fully qualified image:tag  -> prints sha256:<hex> of the index manifest
  # Piped straight into Python: the digest is over the exact bytes (command substitution would
  # strip trailing newlines and produce a wrong digest).
  skopeo inspect --raw "docker://$1" | python3 -c '
import hashlib, json, sys
data = sys.stdin.buffer.read()
media = json.loads(data).get("mediaType", "")
if "index" not in media and "manifest.list" not in media:
    sys.exit(f"not a multi-arch index ({media}); refusing to pin a single-arch digest")
print("sha256:" + hashlib.sha256(data).hexdigest())'
}

echo "Resolving digests (read-only registry queries)..."
d314="$(digest_of docker.io/library/python:3.14-slim)"
d313="$(digest_of docker.io/library/python:3.13-slim)"
duv="$(digest_of "ghcr.io/astral-sh/uv:$uv_version")"
printf '  python:3.14-slim       %s\n  python:3.13-slim       %s\n  uv:%-18s %s\n' "$d314" "$d313" "$uv_version" "$duv"

D314="$d314" D313="$d313" DUV="$duv" WRITE="$WRITE" COPIER_YML="$ROOT/copier.yml" python3 - <<'PY'
import difflib, os, re, sys
path = os.environ["COPIER_YML"]
old = open(path).read()
new, n1 = re.subn(r"\{'3\.14': '[^']*', '3\.13': '[^']*'\}",
                  "{'3.14': '%s', '3.13': '%s'}" % (os.environ["D314"], os.environ["D313"]), old)
new, n2 = re.subn(r"(uv_image_digest:\n(?:  .*\n)*?  default: )\S+", r"\g<1>" + os.environ["DUV"], new)
if (n1, n2) != (1, 1):
    sys.exit(f"copier.yml anchors not found (python={n1}, uv={n2}); nothing changed")
diff = "".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True), "copier.yml", "copier.yml"))
print(diff or "copier.yml already up to date")
if os.environ["WRITE"] == "1" and diff:
    open(path, "w").write(new)
    print("Written. Review with `git diff copier.yml`, then run `mise run template-ci`.")
elif diff:
    print("Dry run only. Re-run with `-- --write` to apply.")
PY
