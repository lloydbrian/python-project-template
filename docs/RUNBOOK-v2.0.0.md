# Runbook: release python-project-template v2.0.0

> **Closed (2026-11-25):** v2.0.0 is released (`8e4d1a6`, release run 45720703997) and the reference app `template-repo` runs it (`13fdf39`). This runbook is kept as the record of how v2.0.0 was delivered and is no longer updated; current state and every release since are in [`docs/RELEASES.md`](RELEASES.md).

The **operator** (LBD) runs every step on the Mac. Claude built, tested and reviewed the change. It pushed, tagged and renamed nothing.

Each step has a **pre-flight** (check before), the **command**, **Expect** (what success looks like), a **Stop if**, and a **post-flight** where useful. Commands that change anything outside your working tree are marked **[changes remote]**, with how to undo them.

**Status (2026-11-24):** steps 0–7 ran for `v2.0.0-rc.1`. Step 8 found a template bug (blank values in a v1 `.env.dev` crashed the service), so step 7b cut `v2.0.0-rc.2`. Step 8.5's test release then found that trivy cannot read the release's OCI archive file, so `v2.0.0-rc.3` fixes the release scan (same 7b path) and steps 8–10 continue from rc.3. From rc.2 on, every operator block is a guarded function (state checks first, `STOP: <reason>` with no changes, `&&` between changes), reviewed and tested in zsh and bash before it is shared. Run verification and commit blocks separately: a block that commits must only be run after the block before it printed its pass line.

**Every step starts the same way.** The first line loads `~/.runbook-v2.env` (written in step 0) and moves into the right folder, then prints it. Steps therefore work in any new terminal, and after step 6 renames the folder they land in `python-project-template` automatically.

**Folders over time:**

| Steps | Template repo folder (`$TPL`) | Reference app folder (`$REF`) |
|---|---|---|
| 0–5 | `~/Developer/repositories/template-repo-files` | `~/Developer/repositories/template-repo` |
| 6–10 | `~/Developer/repositories/python-project-template` (renamed in step 6) | unchanged |

**No secrets are needed** except your existing `gh` login (keychain). If a step ever needs a token, declare it into a variable without echoing it (`read -rs GH_TOKEN && export GH_TOKEN`) and `unset GH_TOKEN` afterwards. Never put a token in a file, a commit or a chat. `~/.runbook-v2.env` holds folder paths and your GitHub owner name only.

**Shell safety:** interactive zsh and bash treat `!` inside double quotes as a history reference (`zsh: illegal modifier`). Every command here single-quotes such text, and `~/.runbook-v2.env` also turns history expansion off for the shell that loads it. `mise run lint` rejects new doc commands that would trip on it.

**Redact before sharing output:**

```bash
redact() { sed -E -e "s#$HOME#~#g" -e 's/[0-9]{12}/<ACCOUNT>/g' -e 's/gh[pousr]_[A-Za-z0-9]{20,}/<TOKEN>/g' -e 's/([0-9]{1,3}\.){3}[0-9]{1,3}/<IP>/g'; }
# usage:  some-command 2>&1 | redact
```

---

## 0. Settings file and pre-flight (once)

```bash
cat > "$HOME/.runbook-v2.env" <<'ENV'
# Runbook v2.0.0 settings: folder paths only, no secrets. Step 6 updates TPL.
export DL="$HOME/Downloads"                       # where the delivery files are
export REPOS="$HOME/Developer/repositories"
export TPL="$REPOS/template-repo-files"           # step 6 changes this to $REPOS/python-project-template
export REF="$REPOS/template-repo"
export OWNER="lloydbrian"
# Copier at the pinned version, without a global install (works in zsh and bash)
copier() { uvx --from copier==9.19.1 copier "$@"; }
# Commands below contain "!" (e.g. 'feat!:'): turn off history expansion in this shell.
if [ -n "${ZSH_VERSION:-}" ]; then setopt NO_BANG_HIST; elif [ -n "${BASH_VERSION:-}" ]; then set +H; fi
# zsh: treat "# ..." after a pasted command as a comment, not as arguments
if [ -n "${ZSH_VERSION:-}" ]; then setopt INTERACTIVE_COMMENTS; fi
# gh: print inline; a pager hides output from pasted command blocks
export GH_PAGER=cat
redact() { sed -E -e "s#$HOME#~#g" -e 's/[0-9]{12}/<ACCOUNT>/g' -e 's/gh[pousr]_[A-Za-z0-9]{20,}/<TOKEN>/g' -e 's/([0-9]{1,3}\.){3}[0-9]{1,3}/<IP>/g'; }
ENV
source "$HOME/.runbook-v2.env" && cd "$REPOS" && pwd
echo "DL=$DL | TPL=$TPL | REF=$REF | OWNER=$OWNER"
mise --version; uv --version; copier --version; podman --version; skopeo --version
gh auth status 2>&1 | head -3
podman machine list
git -C "$TPL" status --short --branch
git -C "$REF" status --short --branch
```

**Expect:**
- the variables print with values, and `pwd` prints your repositories folder;
- mise 2026.11.x, uv 0.13.9, copier 9.19.1, and versions for Podman and skopeo (`brew install skopeo` if missing);
- `gh` reports `Logged in to github.com`;
- the Podman machine shows `Currently running` (`podman machine start` if not);
- both repos show `## main...origin/main` with no file lines (before step 2), or `## feat/v2-copier-template` for the template repo (after step 2).

**Stop if:** a repo has uncommitted changes.

---

## 1. Confirm the delivery

```bash
source "$HOME/.runbook-v2.env" && cd "$DL" && pwd
grep '"head"' MANIFEST.json
shasum -a 256 -c SHA256SUMS
git -C "$TPL" bundle verify "$DL/template-repo-files-v2.bundle"
```

**Expect:**
- `"head"` names the commit in the delivery message;
- every line ends `OK`;
- `... template-repo-files-v2.bundle is okay`, and it requires `af08824` (v1 `main`, which you have).

**Stop if:** any checksum fails.

---

## 2. Apply the bundle to a new branch (local only)

```bash
source "$HOME/.runbook-v2.env" && cd "$TPL" && pwd
git fetch "$DL/template-repo-files-v2.bundle" feat/v2-copier-template:feat/v2-copier-template
git switch feat/v2-copier-template
mise trust && mise install            # this folder's pinned tools (trust is per folder path)
git --no-pager log --oneline -8
DL="$DL" python3 - <<'PY'
import hashlib, json, os, pathlib, sys
m = json.load(open(pathlib.Path(os.environ["DL"]) / "MANIFEST.json"))
bad = [p for p, h in m["files"].items() if hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest() != h]
missing = [p for p in m["deleted"] if pathlib.Path(p).exists()]
print("manifest:", "OK" if not (bad or missing) else f"MISMATCH {bad} still-present {missing}")
sys.exit(1 if bad or missing else 0)
PY
git status --short --branch
```

**Already on the branch from an earlier delivery?** Fetch the newer bundle onto it instead: `git fetch "$DL/template-repo-files-v2.bundle" feat/v2-copier-template && git merge --ff-only FETCH_HEAD`. This fast-forwards it; your branch has no commits of its own yet.

**Expect:** the log's top commit equals `"head"` in `MANIFEST.json`; `manifest: OK`; a clean `## feat/v2-copier-template`.

**Undo** (local only): `git switch main && git branch -D feat/v2-copier-template`.

---

## 3. Full gate on your Mac (includes Podman)

This is the first run with real image builds and model downloads: allow 20–40 minutes. Everything goes to log files, and only summary lines are printed.

```bash
source "$HOME/.runbook-v2.env" && cd "$TPL" && pwd
mise run template-ci 2>&1 | tee /tmp/step3-template-ci.log \
  | grep -E 'render-test .*: PASS|negative controls:|update-test:|check_pins|^FAIL|Error|error:'
for v in service notebooks service-py313 service-ai-lancedb notebooks-ai-chromadb; do
  REQUIRE_CONTAINER=1 mise run render-test -- "$v" 2>&1 | tee "/tmp/step3-$v.log" \
    | grep -E 'render-test .*: PASS|baked model|smoke: OK|Total: [0-9]+ \(|^FAIL|Error|error:'
done
```

**Expect:**
- `render-test <variant>: PASS` for all 8 variants, then `negative controls: 24/24 caught`, `update-test: ... PASS` and `check_pins: OK`;
- each container run passes; `service` and `service-py313` print `smoke: OK`;
- the two AI variants print `baked model: OK (offline, read-only)`;
- trivy prints `Total:` lines and exits 0. It fails only on fixable HIGH or CRITICAL findings.

Rendered projects go to Python's temp folder: on macOS that is `$TMPDIR/python-project-template-render/<variant>` (under `/var/folders/...`), not `/tmp`. Find it with `python3 -c 'import tempfile; print(tempfile.gettempdir())'`.

**Stop if:** anything prints `FAIL` or `Error`. Paste `tail -40` of that log through `redact`. If trivy fails, paste its table; do not add exceptions yet.

---

## 4. Pin the base images by digest (local only)

```bash
source "$HOME/.runbook-v2.env" && cd "$TPL" && pwd
git branch --show-current                     # feat/v2-copier-template
mise run pin-images                           # DRY RUN: four digests and the copier.yml diff; changes nothing
```

Review the dry run, then apply:

```bash
source "$HOME/.runbook-v2.env" && cd "$TPL" && pwd
mise run pin-images -- --write
git --no-pager diff copier.yml
python3 scripts/check_pins.py && REQUIRE_CONTAINER=1 mise run render-test -- service 2>&1 | tail -3
git add copier.yml && git commit -m "chore: pin base images by multi-arch digest"
```

**Expect:**
- the dry run shows `python:3.13-slim`, `python:3.14-slim`, `python:3.15-slim` and `uv:0.13.9`, each with a `sha256:` digest;
- the diff touches only the `python_digest` line (three digests) and the `uv_image_digest` line;
- the service render still passes, now with `FROM ...@sha256:`.

**Stop if:** the script says `not a multi-arch index`. It refuses to pin single-arch digests.
**Undo** (before the commit): `git checkout copier.yml`.

---

## 5. Release-candidate ref, push, open the PR **[changes remote]**

The release gate requires `template_ref` to equal the tag being pushed, so the rc gets its own ref.

```bash
source "$HOME/.runbook-v2.env" && cd "$TPL" && pwd
git branch --show-current                                               # feat/v2-copier-template
sed -i '' 's/^  default: v2.0.0$/  default: v2.0.0-rc.1/' copier.yml     # macOS sed
grep -n -A3 '^template_ref:' copier.yml                                 # default: v2.0.0-rc.1
python3 scripts/check_pins.py --release --tag v2.0.0-rc.1               # check_pins: OK (release)
git commit -am "chore: release candidate v2.0.0-rc.1"
git push -u origin feat/v2-copier-template
gh pr create --base main --head feat/v2-copier-template --title 'feat!: python-project-template v2.0.0 (Copier)' --body-file docs/PR-v2.0.0.md
sleep 20 && gh pr checks --watch
```

**Expect:**
- the `sed` changes exactly one line;
- `check_pins: OK (release)`;
- the PR's `template-ci` passes: `lint`, `render` (8 jobs), `negative-controls` and `update`.

**Stop if:** any check fails. Review the failing job log through `redact`.
**Undo:** close the PR, then `git push origin --delete feat/v2-copier-template`.

---

## 6. Merge, rename the repo and the local folder **[changes remote]**

**6a. Pre-flight** (read-only):

```bash
source "$HOME/.runbook-v2.env" && cd "$TPL" && pwd
git status --short | wc -l | tr -d ' '
git rev-parse --abbrev-ref HEAD
git fetch origin && git rev-list --count origin/feat/v2-copier-template..HEAD
gh pr checks 2; echo "checks exit=$?"
gh pr view 2 --json state,mergeable,headRefOid -q '.state + " " + .mergeable + " " + .headRefOid[0:7]'
gh repo view "$OWNER/template-repo-files" --json visibility -q .visibility
gh repo view "$OWNER/python-project-template" --json name -q .name 2>&1 | head -1
```

**Expect:** `0` uncommitted files, the branch `feat/v2-copier-template`, `0` unpushed commits, every check passing (`checks exit=0`), `OPEN MERGEABLE <head>`, the visibility (note `PRIVATE` for step 9), and "Could not resolve to a Repository", which means the new name is free.

**6a. Merge and rename on GitHub:**

```bash
source "$HOME/.runbook-v2.env" && cd "$TPL" && pwd
gh pr merge 2 --squash --delete-branch
gh repo rename python-project-template -R "$OWNER/template-repo-files" --yes
gh pr view 2 -R "$OWNER/python-project-template" --json state,mergeCommit -q '.state + " " + .mergeCommit.oid[0:7]'
```

**Expect:** `Squashed and merged`, the local and remote branches deleted, `Renamed repository`, then `MERGED <sha>`. Note the SHA: step 7 tags it. With `-R`, gh does not change your local remotes; 6b does. GitHub redirects the old name until a repo with that name is created again, so do not reuse it.

**6b. Rename the local folder and repoint every remote.** Close any editor or terminal open inside the old folder first. Pre-flight:

```bash
source "$HOME/.runbook-v2.env" && cd "$REPOS" && pwd
git -C "$TPL" --no-pager log --oneline -1
git -C "$TPL" status --short | wc -l | tr -d ' '
test -e "$REPOS/python-project-template" && echo "STOP: target already exists" || echo "target free"
git -C "$TPL" remote -v
```

A clone can have more than one remote for the same repo (for example `origin` over SSH and `upstream` over HTTPS). The loop below rewrites only the repo name in each URL and keeps its form. Adjust the remote names to what `git remote -v` showed.

```bash
source "$HOME/.runbook-v2.env" && cd "$REPOS" && pwd
mv template-repo-files python-project-template
sed -i.bak 's|^export TPL=.*|export TPL="$REPOS/python-project-template"   # renamed in step 6|' "$HOME/.runbook-v2.env"
source "$HOME/.runbook-v2.env" && cd "$TPL" && pwd
for r in origin upstream; do git remote set-url "$r" "$(git remote get-url "$r" | sed 's/template-repo-files/python-project-template/')"; done
git remote -v
gh repo set-default "$OWNER/python-project-template"
git pull --ff-only
mise trust && mise install
```

A `mise WARN ... is not trusted` line right after the `cd` is expected: the shell hook runs before `mise trust` does.

**Post-flight:**

```bash
source "$HOME/.runbook-v2.env" && cd "$TPL" && pwd
git remote -v
gh repo set-default --view
git fetch --all --prune && git status -sb | head -1
git --no-pager log --oneline -1
test -e "$REPOS/template-repo-files" && echo "WARN: old folder still present" || echo "old folder gone"
mise tasks >/dev/null && echo "mise tasks: OK"
```

**Expect:** every remote URL names `python-project-template`, the gh default is `lloydbrian/python-project-template`, `## main...origin/main` with no ahead or behind, the merge commit on top, `old folder gone`, `mise tasks: OK`.

**Undo:** `mv python-project-template template-repo-files` (from `$REPOS`), `cp ~/.runbook-v2.env.bak ~/.runbook-v2.env`, and set each remote URL back.

**6c. Protect what projects depend on [changes remote].** Generated projects call the shared workflows by tag, so a tag must never move: a `v*` tag ruleset with **no bypass list** (ADR 0007). `main` requires a PR and the 11 template checks, bound to GitHub Actions (app id 15368) so no other app can satisfy them; admins keep their bypass on `main` for recovery, because every release still runs the full `template-ci` before `publish`.

Dry run: build the payloads from the PR's real check runs (no names typed by hand) and validate them.

```bash
source "$HOME/.runbook-v2.env" && cd "$TPL" && pwd
work=$(mktemp -d) && echo "payloads in: $work"
gh api "repos/$OWNER/python-project-template/commits/<pr-head-sha>/check-runs?per_page=100" \
  --jq '[.check_runs[] | {context: .name, app_id: .app.id}] | unique_by(.context)' > "$work/checks.json"
python3 -c 'import json,sys; c=json.load(open(sys.argv[1])); print(len(c), "checks; app ids:", sorted({x["app_id"] for x in c})); [print("  ", x["context"]) for x in c]' "$work/checks.json"
printf '{"required_status_checks":{"strict":false,"checks":%s},"enforce_admins":false,"required_pull_request_reviews":{"required_approving_review_count":0},"restrictions":null,"allow_force_pushes":false,"allow_deletions":false}\n' "$(cat "$work/checks.json")" > "$work/branch.json"
printf '%s\n' '{"name":"release-tags","target":"tag","enforcement":"active","bypass_actors":[],"conditions":{"ref_name":{"include":["refs/tags/v*"],"exclude":[]}},"rules":[{"type":"update"},{"type":"deletion"}]}' > "$work/tags.json"
python3 -m json.tool "$work/branch.json" >/dev/null && echo "branch.json: valid"
python3 -m json.tool "$work/tags.json" >/dev/null && echo "tags.json: valid"
gh api "repos/$OWNER/python-project-template/rulesets" --jq '[.[] | select(.name=="release-tags")] | length'
```

**Expect:** `11 checks; app ids: [15368]` with the 11 job names (`lint`, `negative-controls`, `update`, eight `render (...)`), both files valid, and `0` (no ruleset yet; a second `POST` would duplicate it).

Apply, in the same terminal (it reuses `$work`):

```bash
source "$HOME/.runbook-v2.env" && cd "$TPL" && pwd && echo "using: $work"
gh api -X POST "repos/$OWNER/python-project-template/rulesets" --input "$work/tags.json" --jq '"created ruleset " + (.id|tostring) + " " + .name'
gh api -X PUT "repos/$OWNER/python-project-template/branches/main/protection" --input "$work/branch.json" --jq '"protected main: " + (.required_status_checks.contexts | length | tostring) + " required checks"'
```

Post-flight:

```bash
source "$HOME/.runbook-v2.env" && cd "$TPL" && pwd
id=$(gh api "repos/$OWNER/python-project-template/rulesets" --jq '.[] | select(.target=="tag") | .id' | head -1); echo "tag ruleset id: ${id:-NONE}"
gh api "repos/$OWNER/python-project-template/rulesets/$id" --jq '{name, enforcement, include: .conditions.ref_name.include, rules: [.rules[].type], bypass: .bypass_actors}'
gh api "repos/$OWNER/python-project-template/branches/main/protection" --jq '{checks: (.required_status_checks.contexts | sort), strict: .required_status_checks.strict, pr_required: (.required_pull_request_reviews != null), admins_enforced: .enforce_admins.enabled, force_push: .allow_force_pushes.enabled}'
```

**Expect:** `release-tags`, `active`, `refs/tags/v*`, `update` and `deletion`, `"bypass": []`; the 11 checks, `strict: false`, `pr_required: true`, `admins_enforced: false`, `force_push: false`.

**Undo:** `gh api -X DELETE "repos/$OWNER/python-project-template/rulesets/$id"` and `gh api -X DELETE "repos/$OWNER/python-project-template/branches/main/protection"` (settings only).

---

## 7. Tag a release candidate **[changes remote]**

`main` is protected, so every change reaches it by PR; tags are cut from the merged commit. Pre-flight (read-only apart from a fast-forward pull). Set `RC` to the candidate being cut:

```bash
source "$HOME/.runbook-v2.env" && cd "$TPL" && pwd
RC=v2.0.0-rc.1
git switch main && git pull --ff-only
git --no-pager log --oneline -1
git status --short | wc -l | tr -d ' '
grep -n -A3 '^template_ref:' copier.yml
python3 scripts/check_pins.py --release --tag "$RC"
python3 scripts/changelog_section.py "${RC#v}" | head -3
git tag -l "$RC" | wc -l | tr -d ' '
git ls-remote --tags origin "$RC" | wc -l | tr -d ' '
```

**Expect:** the merge commit on top, `0`, `default:` equal to `$RC`, `check_pins: OK (release)`, the 2.0.0 changelog lines (an rc falls back to its final version's section), `0` and `0`. **Stop if** any differ: once pushed, the tag cannot move.

Tag, push and watch:

```bash
source "$HOME/.runbook-v2.env" && cd "$TPL" && pwd
RC=v2.0.0-rc.1
git tag "$RC" "$(git rev-parse HEAD)"
git push origin "$RC"
run=""; for i in 1 2 3 4 5 6 7 8 9 10 11 12; do run=$(gh run list --workflow release.yml --branch "$RC" --limit 1 --json databaseId -q '.[0].databaseId'); [ -n "$run" ] && break; sleep 5; done; echo "release run: ${run:-NONE}"
[ -n "$run" ] && gh run watch "$run" --exit-status; echo "watch exit=$?"
```

**Expect:** `verify` → `template-ci` (11 jobs) → `publish`, and `watch exit=0`.

Post-flight (proves the release by its artifact):

```bash
source "$HOME/.runbook-v2.env" && cd "$TPL" && pwd
RC=v2.0.0-rc.1
gh release view "$RC" --json tagName,isPrerelease,isDraft -q '"\(.tagName) prerelease=\(.isPrerelease) draft=\(.isDraft)"'
gh api "repos/$OWNER/python-project-template/git/ref/tags/$RC" --jq '.object.sha[0:7]'
git rev-parse --short HEAD
```

**Expect:** `prerelease=true draft=false`, and the two SHAs equal.

**If it fails, or step 8 finds a template bug:** fix forward with the next candidate (7b). Never move or delete a published tag.

### 7b. Fix forward to the next candidate (used for rc.2)

rc.1 passed its own release, but step 8 found that a v1 `.env.dev` with blank values (`APP_TITLE=`) crashed the generated service. rc.2 carries that fix plus this runbook's corrections. Deliveries arrive as a patch with a checksum file in `$DL`.

```bash
source "$HOME/.runbook-v2.env" && cd "$DL" && pwd && shasum -a 256 -c SHA256SUMS-0002
source "$HOME/.runbook-v2.env" && cd "$TPL" && pwd
git switch main && git pull --ff-only && git switch -c fix/v2.0.0-rc.2 && git am "$DL/0002-fix-blank-env-values-rc.2.patch" && sed -i '' 's/^  default: v2.0.0-rc.1$/  default: v2.0.0-rc.2/' copier.yml && echo "APPLY: OK"
grep -n -A3 '^template_ref:' copier.yml
python3 scripts/check_pins.py --release --tag v2.0.0-rc.2
mise run lint
mise run negative-controls -- --only settings-blank-values settings-validation
```

Every state-changing line is chained with `&&`, so a failure (for example a branch that already exists from an earlier attempt) stops before `git am` can apply the patch to the wrong branch.

**Expect:** the checksum `OK`, `APPLY: OK`, `default: v2.0.0-rc.2`, `check_pins: OK (release)`, lint passes, `negative controls: 2/2 caught`. **Stop if** any fail; nothing has left the Mac yet. **Undo:** `git switch main && git branch -D fix/v2.0.0-rc.2`.

Commit, push and open the PR (separate block: run it only after the one above passes):

```bash
source "$HOME/.runbook-v2.env" && cd "$TPL" && pwd
git commit -am 'chore: release candidate v2.0.0-rc.2'
git push -u origin fix/v2.0.0-rc.2
gh pr create --base main --head fix/v2.0.0-rc.2 --title 'fix: blank env values fall back to defaults (v2.0.0-rc.2)' --body 'Found adopting v2 in template-repo at rc.1: a v1 .env.dev with APP_TITLE= crashed the service at import. Settings now treat blank values as unset (env_ignore_empty) and reject empty titles. Adds a test, a negative control (24 total) and runbook corrections from the rc.1 run.'
sleep 20; gh pr checks fix/v2.0.0-rc.2 --watch; echo "checks exit=$?"
gh pr merge fix/v2.0.0-rc.2 --squash --delete-branch
```

Then run step 7 again with `RC=v2.0.0-rc.2` (pre-flight, tag, watch, post-flight).

---

## 8. Regenerate the reference app from the rc **[changes remote at the end]**

`template-repo` becomes a project generated from the template. Its folder name does not change. The v1 files are replaced on a branch; `main` is untouched until you merge.

**8.1 Pre-flight** (read-only):

```bash
source "$HOME/.runbook-v2.env" && cd "$REF" && pwd
git status --short --branch
git remote -v
gh repo view "$OWNER/template-repo" --json visibility -q .visibility
ls -l "$DL/template-repo.answers.yml" && grep -n 'python_version' "$DL/template-repo.answers.yml"
gh api "repos/$OWNER/template-repo/branches/main/protection" --jq '.required_status_checks.contexts' 2>&1 | head -3
gh api "repos/$OWNER/template-repo/rulesets" --jq '.[] | [.id, .name, .target, .enforcement] | @tsv'
git ls-remote --tags origin v0.1.0 | wc -l | tr -d ' '
ls -l .env.dev 2>&1 && sed -E 's/=.*/=<value hidden>/' .env.dev
```

**Expect:** a clean `## main...origin/main`; the remotes (with more than one, run `gh repo set-default "$OWNER/template-repo"`); the visibility; `python_version: "3.15"`; protection `404` or `["check"]`; any rulesets (a tag ruleset would block 8.5); `0`; and the **names** in your existing `.env.dev`. It is git-ignored and survives the regeneration; from rc.2, blank values in it fall back to defaults.

**8.2 Regenerate and gate** (local only). `git rm -r -q .` deletes the tracked files from this branch's working folder; all of them stay in git on `main`, and untracked or ignored files (`.env.dev`, `.venv`) are not touched.

```bash
source "$HOME/.runbook-v2.env" && cd "$DL" && pwd && grep ' template-repo.answers.yml$' SHA256SUMS | shasum -a 256 -c -
source "$HOME/.runbook-v2.env" && cd "$REF" && pwd
git switch -c feat/v2-generated
git rm -r -q .
copier copy --vcs-ref v2.0.0-rc.2 --data-file "$DL/template-repo.answers.yml" --defaults --overwrite "gh:$OWNER/python-project-template" .
mise trust && mise install && mise run bootstrap
mise run ci && REQUIRE_CONTAINER=1 mise run image && mise run scan && mise run smoke && echo "GATES: PASS"
grep -E '_commit|_src_path' .copier-answers.yml
```

**Already rendered from an earlier rc on this branch?** Move it forward instead of re-copying, which also exercises the update path generated projects use:

```bash
source "$HOME/.runbook-v2.env" && cd "$REF" && pwd
git switch feat/v2-generated && git status --short | wc -l | tr -d ' '
copier update --vcs-ref v2.0.0-rc.2 --skip-answered --defaults
git --no-pager diff --stat
mise run ci && REQUIRE_CONTAINER=1 mise run image && mise run scan && mise run smoke && echo "GATES: PASS"
grep -E '_commit|_src_path' .copier-answers.yml
```

**Expect:** `GATES: PASS` as the last gate line, `smoke: OK`, `_commit: v2.0.0-rc.2`, `_src_path: gh:lloydbrian/python-project-template`. **Stop if** `GATES: PASS` is missing: do not commit. **Undo** (before committing): `git switch -f main && git branch -D feat/v2-generated`.

**8.3 Commit** (only after `GATES: PASS`):

```bash
source "$HOME/.runbook-v2.env" && cd "$REF" && pwd
git add -A && git status --short | wc -l | tr -d ' '
git commit -m 'feat!: regenerate from python-project-template v2.0.0-rc.2'
```

**8.4 Push and open the PR [changes remote].** If 8.1 showed `["check"]`, first switch the required check to the v2 name:

```bash
source "$HOME/.runbook-v2.env" && cd "$REF" && pwd
gh api -X PATCH "repos/$OWNER/template-repo/branches/main/protection/required_status_checks" -f 'contexts[]=check / check' --jq '.contexts'
```

```bash
source "$HOME/.runbook-v2.env" && cd "$REF" && pwd
git push -u origin feat/v2-generated
gh pr create -R "$OWNER/template-repo" --base main --head feat/v2-generated --title 'feat!: regenerate from python-project-template v2.0.0-rc.2' --body 'Regenerates the reference app from python-project-template v2.0.0-rc.2. /health becomes /health/live and /health/ready.'
sleep 20; gh pr checks feat/v2-generated -R "$OWNER/template-repo" --watch; echo "checks exit=$?"
```

**Expect:** the check `check / check` passes (it calls `python-ci.yml@v2.0.0-rc.2`), `checks exit=0`.

**Behaviour change:** `/health` is replaced by `/health/live` and `/health/ready`. Update anything that probes `/health`.

**8.5 Exercise the release path once [changes remote].** Nothing else runs `python-release.yml` before a real project tags.

```bash
source "$HOME/.runbook-v2.env" && cd "$REF" && pwd
git branch --show-current
grep -n '^version' pyproject.toml
git tag v0.1.0 && git push origin v0.1.0
run=""; for i in 1 2 3 4 5 6 7 8 9 10 11 12; do run=$(gh run list --workflow release.yml --branch v0.1.0 --limit 1 --json databaseId -q '.[0].databaseId'); [ -n "$run" ] && break; sleep 5; done; echo "release run: ${run:-NONE}"
[ -n "$run" ] && gh run watch "$run" --exit-status; echo "watch exit=$?"
gh release view v0.1.0 --json assets -q '.assets[].name'
```

**Expect:** both `build` jobs (amd64, arm64) and `publish` pass; `attest` passes on a public repo or is skipped on a private one; five assets: two `.oci.tar`, two `.sbom.cdx.json`, `SHA256SUMS`.

**8.6 Remove the test release [changes remote, deletes].** Audit, then delete only `v0.1.0` in `template-repo`:

```bash
source "$HOME/.runbook-v2.env" && cd "$REF" && pwd
gh release view v0.1.0 -R "$OWNER/template-repo" --json tagName,createdAt,assets -q '"\(.tagName) created=\(.createdAt) assets=\(.assets | length)"'
```

**Expect:** `v0.1.0`, created minutes ago, `assets=5`. Then:

```bash
source "$HOME/.runbook-v2.env" && cd "$REF" && pwd
gh release delete v0.1.0 -R "$OWNER/template-repo" --yes --cleanup-tag
git tag -d v0.1.0
git ls-remote --tags origin v0.1.0 | wc -l | tr -d ' '
```

**Expect:** the release and the remote and local tags are gone; `0`.

---

## 9. Private template repo only: allow workflow access

Skip this step if the template repo is public.

GitHub → `python-project-template` → *Settings → Actions → General → Access* → **Accessible from repositories owned by the user 'lloydbrian'** → Save. Then re-run the reference app's checks:

```bash
source "$HOME/.runbook-v2.env" && cd "$REF" && pwd
gh run rerun "$(gh run list --branch feat/v2-generated --limit 1 --json databaseId -q '.[0].databaseId')" --failed
```

---

## 10. Final release **[changes remote]**

The final release changes only `template_ref`: everything else shipped, and was exercised, in the last rc.

**10.1 Merge the reference app PR:**

```bash
source "$HOME/.runbook-v2.env" && cd "$REF" && pwd
gh pr checks feat/v2-generated -R "$OWNER/template-repo"; echo "checks exit=$?"
gh pr merge feat/v2-generated -R "$OWNER/template-repo" --squash --delete-branch
```

**10.2 Release branch in the template:**

```bash
source "$HOME/.runbook-v2.env" && cd "$TPL" && pwd
git switch main && git pull --ff-only && git switch -c chore/release-v2.0.0
sed -i '' 's/^  default: v2.0.0-rc.2$/  default: v2.0.0/' copier.yml
git --no-pager diff --stat
python3 scripts/check_pins.py --release --tag v2.0.0
```

**Expect:** one line changed in `copier.yml`, `check_pins: OK (release)`. Then:

```bash
source "$HOME/.runbook-v2.env" && cd "$TPL" && pwd
git commit -am 'chore: release v2.0.0'
git push -u origin chore/release-v2.0.0
gh pr create --base main --head chore/release-v2.0.0 --title 'chore: release v2.0.0' --body 'Sets template_ref to v2.0.0. Everything else shipped in v2.0.0-rc.2.'
sleep 20; gh pr checks chore/release-v2.0.0 --watch; echo "checks exit=$?"
gh pr merge chore/release-v2.0.0 --squash --delete-branch
```

**10.3 Tag v2.0.0:** run step 7 with `RC=v2.0.0`. **Expect** in its post-flight: `prerelease=false`. Also:

```bash
source "$HOME/.runbook-v2.env" && cd "$TPL" && pwd
git show v2.0.0:copier.yml | grep -A3 '^template_ref:'
git show v2.0.0:copier.yml | grep -c 'sha256:PENDING'
```

**Expect:** `default: v2.0.0`; `1` (the comment only, no digest).

**10.4 Move the reference app to v2.0.0:**

```bash
source "$HOME/.runbook-v2.env" && cd "$REF" && pwd
git switch main && git pull --ff-only && git switch -c chore/template-v2.0.0
copier update --vcs-ref v2.0.0 --skip-answered --defaults
git --no-pager diff --stat
git --no-pager diff | grep -E '^[-+][^-+]' | grep -vE 'rc\.2|v2\.0\.0' | head
mise run ci && echo "GATES: PASS"
```

**Expect:** only `.copier-answers.yml`, `ci.yml`, `release.yml`, `.mise.toml` (header comment), `README.md` and `CHANGELOG.md` change; the filtered `grep` prints nothing; `GATES: PASS`. Then:

```bash
source "$HOME/.runbook-v2.env" && cd "$REF" && pwd
git commit -am 'chore: update to python-project-template v2.0.0'
git push -u origin chore/template-v2.0.0
gh pr create -R "$OWNER/template-repo" --base main --head chore/template-v2.0.0 --title 'chore: update to python-project-template v2.0.0' --body 'copier update from v2.0.0-rc.2 to v2.0.0.'
sleep 20; gh pr checks chore/template-v2.0.0 -R "$OWNER/template-repo" --watch; echo "checks exit=$?"
gh pr merge chore/template-v2.0.0 -R "$OWNER/template-repo" --squash --delete-branch
```

**10.5 Optional: protect the reference app's `main`** with the v2 check, the same way as the template (6c): required check `check / check` bound to app id 15368, PR required.

**10.6 Release log** (through a PR, because `main` is protected):

```bash
source "$HOME/.runbook-v2.env" && cd "$TPL" && pwd
git switch main && git pull --ff-only && git switch -c docs/release-log-v2.0.0
printf '| %s | v2.0.0 | %s | %s | %s | %s |\n' "$(date +%F)" "$(git rev-parse --short v2.0.0)" 'same day (first v2 commit 2026-11-24)' 'fix-forward: rc.2 (blank env values)' '8/8 variants, 24/24 controls, update PASS' >> docs/RELEASES.md
tail -2 docs/RELEASES.md
git commit -am 'docs: release log v2.0.0'
git push -u origin docs/release-log-v2.0.0
gh pr create --base main --head docs/release-log-v2.0.0 --title 'docs: release log v2.0.0' --body 'Release record for v2.0.0.'
sleep 20; gh pr checks docs/release-log-v2.0.0 --watch; echo "checks exit=$?"
gh pr merge docs/release-log-v2.0.0 --squash --delete-branch
```

**10.7 Optional local tidy-up.** `~/.runbook-v2.env` and its `.bak` hold paths only. To remove them, check with `ls -l "$HOME/.runbook-v2.env" "$HOME/.runbook-v2.env.bak"`, then `rm -i` the two files (it asks per file). The `mktemp -d` folder from 6c is in macOS's temp area, which the system clears.

---

## Rollback

| What | How | Notes |
|---|---|---|
| Template release | `gh release delete vX --yes`; removing the tag needs the `release-tags` ruleset switched off on purpose (*Settings → Rules*), then on again | Prefer releasing a fix (`v2.0.1`) over deleting a tag projects may use |
| Repo rename | See step 6 *Undo* (GitHub and local folder) | Generated projects reference the new name; renaming back breaks their `uses:` unless GitHub's redirect applies |
| Reference app | `git revert` the merge commit in `template-repo` | v1 files return |
| v2 merge in the template | `git revert -m 1 <merge>` | Only before any project has generated from v2 |

**Do not roll back** the `.gitignore` hardening or the base-image pins. Those changes reduce risk on their own.

## Release log entry

Step 10.6 appends the row to `docs/RELEASES.md` through a PR, because `main` is protected.
