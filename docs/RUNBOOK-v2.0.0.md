# Runbook: release python-project-template v2.0.0

The **operator** (LBD) runs every step on the Mac. Claude built, tested and reviewed the change. It pushed, tagged and renamed nothing.

Each step has a **pre-flight** (check before), the **command**, **Expect** (what success looks like), a **Stop if**, and a **post-flight** where useful. Commands that change anything outside your working tree are marked **[changes remote]**, with how to undo them.

**Every step starts the same way.** The first line loads `~/.runbook-v2.env` (written in step 0) and moves into the right folder, then prints it. Steps therefore work in any new terminal, and after step 6 renames the folder they land in `python-project-template` automatically.

**Folders over time:**

| Steps | Template repo folder (`$TPL`) | Reference app folder (`$REF`) |
|---|---|---|
| 0–5 | `~/Developer/repositories/template-repo-files` | `~/Developer/repositories/template-repo` |
| 6–10 | `~/Developer/repositories/python-project-template` (renamed in step 6) | unchanged |

**No secrets are needed** except your existing `gh` login (keychain). If a step ever needs a token, declare it into a variable without echoing it (`read -rs GH_TOKEN && export GH_TOKEN`) and `unset GH_TOKEN` afterwards. Never put a token in a file, a commit or a chat. `~/.runbook-v2.env` holds folder paths and your GitHub owner name only.

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
- `render-test <variant>: PASS` for all 8 variants, then `negative controls: 22/22 caught`, `update-test: ... PASS` and `check_pins: OK`;
- each container run passes; `service` and `service-py313` print `smoke: OK`;
- the two AI variants print `baked model: OK (offline, read-only)`;
- trivy prints `Total:` lines and exits 0. It fails only on fixable HIGH or CRITICAL findings.

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
gh pr create --base main --title "feat!: python-project-template v2.0.0 (Copier)" --body-file docs/PR-v2.0.0.md
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

**Pre-flight:**

```bash
source "$HOME/.runbook-v2.env" && cd "$TPL" && pwd
gh pr checks                                                            # all pass
gh repo view "$OWNER/template-repo-files" --json visibility -q .visibility   # note PRIVATE for step 9
ls -d "$REPOS/python-project-template" 2>/dev/null && echo "STOP: target folder already exists"
```

**6a. Merge and rename on GitHub:**

```bash
source "$HOME/.runbook-v2.env" && cd "$TPL" && pwd
gh pr merge --squash --delete-branch
gh repo rename python-project-template -R "$OWNER/template-repo-files" --yes
```

**6b. Rename the local folder and point everything at it.** `mv` only renames the folder; history and files are untouched.

```bash
source "$HOME/.runbook-v2.env" && cd "$REPOS" && pwd
[ ! -e python-project-template ] && mv template-repo-files python-project-template
sed -i '' 's|^export TPL=.*|export TPL="$REPOS/python-project-template"   # renamed in step 6|' "$HOME/.runbook-v2.env"
source "$HOME/.runbook-v2.env" && cd "$TPL" && pwd                      # .../python-project-template
git remote set-url origin "https://github.com/$OWNER/python-project-template.git"
git switch main && git pull
mise trust && mise install                                              # trust is per folder path
git remote -v && git --no-pager log --oneline -1
```

**Expect:**
- the merge succeeds and `Renamed repository` is printed;
- `pwd` ends in `python-project-template`, and `grep TPL ~/.runbook-v2.env` shows the new path;
- `git remote -v` shows `.../python-project-template.git`; `git pull` brings in the squashed v2 commit on `main`;
- `mise trust` accepts the new folder path.

**Undo:**
- GitHub: `gh repo rename template-repo-files -R "$OWNER/python-project-template" --yes`;
- local: `cd "$REPOS" && mv python-project-template template-repo-files`, restore the `TPL` line in `~/.runbook-v2.env`, and `git remote set-url origin https://github.com/$OWNER/template-repo-files.git`.

**Post-flight: protect what projects depend on.** GitHub → `python-project-template` → *Settings*:
- *Rules → Rulesets → New tag ruleset*: target `v*`; enable **Restrict updates** and **Restrict deletions**; bypass list **Repository admin** only, for emergencies; *Enforcement status* Active. Generated projects call the shared workflows by tag, so a tag must never move. Fix a bad tag by publishing the next one (`-rc.2`, `v2.0.1`).
- *Branches*: protect `main`, with the required checks set to the template's jobs (`lint`, the `render` jobs, `negative-controls`, `update`), not the old `check`.

---

## 7. Tag the release candidate **[changes remote]**

```bash
source "$HOME/.runbook-v2.env" && cd "$TPL" && pwd                      # .../python-project-template
git switch main && git pull
grep -n -A3 '^template_ref:' copier.yml                                 # default: v2.0.0-rc.1
git tag v2.0.0-rc.1 && git push origin v2.0.0-rc.1
sleep 15
gh run watch "$(gh run list --workflow release.yml --branch v2.0.0-rc.1 --limit 1 --json databaseId -q '.[0].databaseId')"
gh release view v2.0.0-rc.1 --json tagName,isPrerelease
```

**Expect:** the `release` workflow passes `verify`, then `template-ci`, then `publish`, and the release shows `"isPrerelease": true`.

**If it fails:** fix on `main`, set `template_ref` to `v2.0.0-rc.2`, and tag `v2.0.0-rc.2`. The tag ruleset blocks moving or deleting `v2.0.0-rc.1`, by design.

---

## 8. Regenerate the reference app from the rc **[changes remote at the end]**

`template-repo` becomes a project generated from the template. Its folder name does not change. The v1 files are replaced on a branch; `main` is untouched until you merge.

```bash
source "$HOME/.runbook-v2.env" && cd "$REF" && pwd                      # .../template-repo
git status --short --branch                                             # clean ## main...origin/main
ls "$DL/template-repo.answers.yml"
git switch -c feat/v2-generated
git ls-files | wc -l                                                    # about 24 v1 files
git rm -r -q .                                                          # stage removal on this branch only
copier copy --vcs-ref v2.0.0-rc.1 --data-file "$DL/template-repo.answers.yml" --defaults --overwrite \
  "gh:$OWNER/python-project-template" .
mise trust && mise install && mise run bootstrap
mise run ci && REQUIRE_CONTAINER=1 mise run image && mise run scan && mise run smoke
grep -E '_commit|_src_path' .copier-answers.yml
git add -A && git commit -m "feat!: regenerate from python-project-template v2.0.0-rc.1"
```

**About `git rm -r -q .`:** it stages deletion of tracked files on the new branch only. Untracked and ignored files (`.env.dev`, `.venv`) are not touched, and `main` keeps every file. To undo before committing: `git switch -f main && git branch -D feat/v2-generated`.

**Expect:**
- `mise run ci` passes and `smoke: OK`;
- `.copier-answers.yml` shows `_commit: v2.0.0-rc.1` and `_src_path: gh:lloydbrian/python-project-template`.

**Behaviour change:** `/health` is replaced by `/health/live` and `/health/ready`. Update anything that probes `/health`.

```bash
source "$HOME/.runbook-v2.env" && cd "$REF" && pwd
git push -u origin feat/v2-generated
gh pr create --base main --title "feat!: regenerate from python-project-template v2.0.0-rc.1" --fill
sleep 20 && gh pr checks --watch
```

**Expect:** the check named **`check / check`** passes; it calls `python-ci.yml@v2.0.0-rc.1`.

**Stop if:**
- `workflow was not found` or `not allowed`: see step 9.
- The PR waits for a check that never comes: `template-repo`'s branch protection still requires the v1 check `check`. Change it to `check / check` (*Settings → Branches*).

**Exercise the release path once before v2.0.0.** Nothing else runs `python-release.yml` before a real project tags.

```bash
source "$HOME/.runbook-v2.env" && cd "$REF" && pwd
git switch feat/v2-generated
git tag v0.1.0 && git push origin v0.1.0                                # pyproject version is 0.1.0
sleep 15
gh run watch "$(gh run list --workflow release.yml --branch v0.1.0 --limit 1 --json databaseId -q '.[0].databaseId')"
gh release view v0.1.0 --json assets -q '.assets[].name'
gh release delete v0.1.0 --yes --cleanup-tag                            # remove the test release
```

**Expect:** both `build` jobs (amd64 and arm64) and `publish` pass; `attest` passes on a public repo or is skipped on a private one; the assets are two `.oci.tar` files, two `.sbom.cdx.json` files and `SHA256SUMS`.

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

Merge the reference app PR first:

```bash
source "$HOME/.runbook-v2.env" && cd "$REF" && pwd
gh pr merge --squash --delete-branch
```

Then release the template:

```bash
source "$HOME/.runbook-v2.env" && cd "$TPL" && pwd                      # .../python-project-template
git switch main && git pull && git switch -c chore/release-v2.0.0
sed -i '' 's/^  default: v2.0.0-rc.1$/  default: v2.0.0/' copier.yml
python3 scripts/check_pins.py --release --tag v2.0.0
git commit -am "chore: release v2.0.0" && git push -u origin chore/release-v2.0.0
gh pr create --base main --fill
sleep 20 && gh pr checks --watch
gh pr merge --squash --delete-branch
git switch main && git pull
git tag v2.0.0 && git push origin v2.0.0
sleep 15
gh run watch "$(gh run list --workflow release.yml --branch v2.0.0 --limit 1 --json databaseId -q '.[0].databaseId')"
```

**Post-flight (prove the release by its artifact):**

```bash
source "$HOME/.runbook-v2.env" && cd "$TPL" && pwd
gh release view v2.0.0 --json tagName,isPrerelease                      # isPrerelease: false
git show v2.0.0:copier.yml | grep -A3 '^template_ref:'                  # default: v2.0.0
git show v2.0.0:copier.yml | grep -c 'sha256:PENDING'                   # 1 (the comment only)
```

Update the reference app to the final release:

```bash
source "$HOME/.runbook-v2.env" && cd "$REF" && pwd
git switch main && git pull && git switch -c chore/template-v2.0.0
copier update --vcs-ref v2.0.0 --skip-answered && git --no-pager diff --stat
```

**Expect:** the update diff replaces `v2.0.0-rc.1` with `v2.0.0`, and nothing else, in `.copier-answers.yml`, `.github/workflows/ci.yml` and `release.yml`, `.mise.toml` (header comment), `README.md` and `CHANGELOG.md`. Commit it, open a PR and merge it once `check / check` passes.

When everything is done, remove the settings file: `rm ~/.runbook-v2.env` (paths only, but no longer needed).

---

## Rollback

| What | How | Notes |
|---|---|---|
| Template release | `gh release delete vX --yes`, then remove the tag (needs your ruleset bypass) | Prefer releasing a fix (`v2.0.1`) over deleting a tag projects may use |
| Repo rename | See step 6 *Undo* (GitHub and local folder) | Generated projects reference the new name; renaming back breaks their `uses:` unless GitHub's redirect applies |
| Reference app | `git revert` the merge commit in `template-repo` | v1 files return |
| v2 merge in the template | `git revert -m 1 <merge>` | Only before any project has generated from v2 |

**Do not roll back** the `.gitignore` hardening or the base-image pins. Those changes reduce risk on their own.

## Release log entry

After step 10, append to `docs/RELEASES.md` in the template repo:

```text
2026-11-xx  v2.0.0  <commit>  lead time: <first commit → tag>  fix-forward/rollback: none  gates: 8/8 variants, 22/22 controls, update PASS
```
