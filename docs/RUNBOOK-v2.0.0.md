# Runbook: release python-project-template v2.0.0

The **operator** (LBD) runs every step on the Mac. Claude built, tested and reviewed the change. It pushed, tagged and renamed nothing.

Each step has a **pre-flight** (check before), the **command**, **Expect** (what success looks like), a **Stop if**, and a **post-flight** (check after). Commands that change anything outside your working tree are marked **[changes remote]** and state whether they can be undone.

**No secrets are needed in this runbook** except your existing `gh` login. If a step ever needs a token, declare it into a variable without echoing it (`read -rs GH_TOKEN && export GH_TOKEN`), and `unset GH_TOKEN` afterwards. Never paste a token into a file, a commit or a chat.

**Redact before sharing output.** If you paste output back for review, pass it through this first:

```bash
redact() { sed -E -e "s#$HOME#~#g" -e 's/[0-9]{12}/<ACCOUNT>/g' -e 's/gh[pousr]_[A-Za-z0-9]{20,}/<TOKEN>/g' -e 's/([0-9]{1,3}\.){3}[0-9]{1,3}/<IP>/g'; }
# usage:  some-command 2>&1 | redact
```

---

## 0. Variables (set once per terminal)

```bash
export DL="$HOME/Downloads"                                  # where you saved the delivery files; change if different
export TPL="$HOME/Developer/repositories/template-repo-files"
export REF="$HOME/Developer/repositories/template-repo"
export OWNER="lloydbrian"
```

**Pre-flight**

```bash
mise --version && uv --version && copier --version && podman --version && skopeo --version && gh auth status 2>&1 | head -3
podman machine list
git -C "$TPL" status --short --branch && git -C "$REF" status --short --branch
```

**Expect:** all tools print versions (`brew install skopeo` if it is missing); the Podman machine is `Currently running`; both repos are on `main`, clean and up to date (`## main...origin/main` with no file lines).
**Stop if:** either repo has uncommitted changes or is behind/ahead of `origin/main`. Commit, stash or pull first.

---

## 1. Confirm the delivery

```bash
cd "$DL"
shasum -a 256 -c SHA256SUMS
git bundle verify template-repo-files-v2.bundle
```

**Expect:** every line `OK`; `The bundle records a complete history` (or `requires` the v1 main commit, `af08824`, which you already have).
**Stop if:** any checksum fails. Do not apply a bundle that does not match.

---

## 2. Apply the bundle to a new branch (local only)

**Pre-flight:** `git -C "$TPL" rev-parse --short HEAD` prints `af08824` (v1 main after PR #1).

```bash
cd "$TPL"
git fetch "$DL/template-repo-files-v2.bundle" feat/v2-copier-template:feat/v2-copier-template
git switch feat/v2-copier-template
git log --oneline -3
git diff --stat main...HEAD | tail -1
python3 - <<'PY'
import hashlib, json, pathlib, sys
m = json.load(open(pathlib.Path.home() / "Downloads" / "MANIFEST.json"))
bad = [p for p, h in m["files"].items() if hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest() != h]
print("manifest:", "OK" if not bad else f"MISMATCH {bad}"); sys.exit(1 if bad else 0)
PY
```

**Expect:** HEAD is the commit named in `MANIFEST.json` (`head`); about 105 files changed; `manifest: OK`.
**Stop if:** the fetch is refused, or the manifest mismatches.
**Undo:** `git switch main && git branch -D feat/v2-copier-template` (local branch only).

---

## 3. Run the full gate on your Mac (includes Podman)

```bash
mise trust && mise install
mise run template-ci                                   # lint, 5 variants, 19 negative controls, update test
REQUIRE_CONTAINER=1 mise run render-test -- service    # image test stage, build, scan, SBOM, smoke
REQUIRE_CONTAINER=1 mise run render-test -- notebooks
```

**Expect:**
- `render-test <variant>: PASS` for all five variants;
- every container variant prints `image_sim: target test: PASS`;
- `negative controls: 19/19 caught`;
- `update-test: ... PASS`;
- with `REQUIRE_CONTAINER=1`: `smoke: OK`, and trivy exits 0.

**Stop if:**
- **trivy reports a fixable HIGH/CRITICAL.** Rebuild first (the image task uses `--pull=newer`). If the finding persists, send the trivy table through `redact` and review it before adding any exception.
- **Anything else fails.** Send the last 40 lines through `redact` for review.

This is the first time the images are built and scanned. The build sandbox could not reach the registries.

---

## 4. Pin the base images by digest

```bash
mise run pin-images                 # DRY RUN: prints three digests and the copier.yml diff
mise run pin-images -- --write      # apply
git diff copier.yml
python3 scripts/check_pins.py && REQUIRE_CONTAINER=1 mise run render-test -- service
git add copier.yml && git commit -m "chore: pin base images by multi-arch digest"
```

**Expect:**
- the dry run shows `python:3.14-slim`, `python:3.13-slim` and `uv:0.13.9` with `sha256:` digests;
- the diff touches only the `python_digest` and `uv_image_digest` lines;
- the re-render's `FROM` line now ends `@sha256:...`;
- the service render still passes.

**Stop if:** the script says `not a multi-arch index`. It refuses to pin single-arch digests.

---

## 5. Set the release-candidate ref, push and open the PR **[changes remote]**

The release gate requires `template_ref` to equal the tag being pushed, so the rc gets its own ref.

```bash
sed -i '' 's/^  default: v2.0.0$/  default: v2.0.0-rc.1/' copier.yml     # macOS sed
grep -n -A3 '^template_ref:' copier.yml                                 # shows default: v2.0.0-rc.1
python3 scripts/check_pins.py --release --tag v2.0.0-rc.1               # check_pins: OK (release)
git commit -am "chore: release candidate v2.0.0-rc.1"
git push -u origin feat/v2-copier-template
gh pr create --base main --title "feat!: python-project-template v2.0.0 (Copier)" --body-file docs/PR-v2.0.0.md
sleep 20 && gh pr checks --watch
```

**Expect:**
- the `sed` changes exactly one line (`grep` shows it);
- `check_pins: OK (release)`;
- the PR runs `template-ci`: `lint`, `render (×5)`, `negative-controls` and `update` all pass.

**Stop if:** any check fails. Review the failing job log through `redact`.
**Undo:** close the PR and delete the remote branch (`git push origin --delete feat/v2-copier-template`).

---

## 6. Merge, then rename the repo **[changes remote]**

**Pre-flight:**
- all PR checks are green;
- `gh repo view "$OWNER/template-repo-files" --json visibility -q .visibility` prints the visibility. If it is `PRIVATE`, note it for step 9.

```bash
gh pr merge --squash --delete-branch
gh repo rename python-project-template -R "$OWNER/template-repo-files" --yes
git switch main && git pull
git remote set-url origin "https://github.com/$OWNER/python-project-template.git"
git remote -v && git fetch origin && git log --oneline -1
```

**Expect:**
- the merge succeeds;
- the rename prints `Renamed repository`;
- `git fetch` works against the new URL. GitHub also redirects the old URL.

**Undo the rename:** `gh repo rename template-repo-files -R "$OWNER/python-project-template" --yes`.

**Post-flight: protect what projects depend on.** GitHub → `python-project-template` → *Settings*:
- *Rules → Rulesets → New tag ruleset*: target `v*`; enable **Restrict updates** and **Restrict deletions**; no bypass list (or only you); set *Enforcement status* to Active. Generated projects call the shared workflows by tag, so a tag must never move.
- *Branches*: branch protection on `main`, with the required checks set to the template's jobs (`lint`, `render (service)` and the rest), not the old `check`.

---

## 7. Tag the release candidate **[changes remote]**

```bash
git tag v2.0.0-rc.1 && git push origin v2.0.0-rc.1
sleep 15   # give GitHub time to register the run
gh run watch "$(gh run list --workflow release.yml --branch v2.0.0-rc.1 --limit 1 --json databaseId -q '.[0].databaseId')"
gh release view v2.0.0-rc.1 --json tagName,isPrerelease
```

**Expect:** the `release` workflow passes `verify`, then `template-ci`, then `publish`. The release shows `"isPrerelease": true`.
**Stop if:** `verify` fails. It names the problem (ref mismatch or PENDING digest).
**Undo:** `gh release delete v2.0.0-rc.1 --yes && git push origin :refs/tags/v2.0.0-rc.1 && git tag -d v2.0.0-rc.1`.

---

## 8. Regenerate the reference app from the rc **[changes remote at the end]**

`template-repo` becomes a project *generated from* the template. Its v1 files are replaced on a branch, so `main` is untouched until you merge.

**Pre-flight:** `git -C "$REF" status --short --branch` is clean on `main`. `ls "$DL/template-repo.answers.yml"` exists.

```bash
cd "$REF"
git switch -c feat/v2-generated
git ls-files | wc -l                       # count before (about 24 files)
git rm -r -q .                             # stage removal of v1 tracked files (branch only; main untouched)
copier copy --vcs-ref v2.0.0-rc.1 --data-file "$DL/template-repo.answers.yml" --defaults \
  "gh:$OWNER/python-project-template" .
mise trust && mise install && mise run bootstrap
mise run ci && REQUIRE_CONTAINER=1 mise run image && mise run scan && mise run smoke
grep -E '_commit|_src_path' .copier-answers.yml
git add -A && git commit -m "feat!: regenerate from python-project-template v2.0.0-rc.1"
```

**Review before running `git rm -r -q .`:**
- it stages deletion of tracked files on the new branch only;
- untracked and ignored files (`.env.dev`, `.venv`) are not touched;
- `main` keeps every file.

Undo before committing with `git switch -f main && git branch -D feat/v2-generated`.

**Expect:**
- `mise run ci` passes;
- `smoke: OK`;
- `.copier-answers.yml` shows `_commit: v2.0.0-rc.1` and `_src_path: gh:lloydbrian/python-project-template`.

**Behaviour change:** `/health` is replaced by `/health/live` and `/health/ready`. Update anything that probes `/health`.

```bash
git push -u origin feat/v2-generated
gh pr create --base main --title "feat!: regenerate from python-project-template v2.0.0-rc.1" --fill
sleep 20 && gh pr checks --watch
```

**Expect:** the check named **`check / check`** passes. It calls `python-ci.yml@v2.0.0-rc.1`.
**Stop if:** `workflow was not found` or `not allowed`. See step 9.
**If the PR waits for a check that never comes:** `template-repo`'s branch protection still requires the v1 check `check`. Change the required check to `check / check` (*Settings → Branches*).

**Exercise the release path once before v2.0.0** (nothing else runs `python-release.yml` before a real project tags):

```bash
git switch feat/v2-generated
git tag v0.1.0 && git push origin v0.1.0         # pyproject version is 0.1.0
sleep 15
gh run watch "$(gh run list --workflow release.yml --branch v0.1.0 --limit 1 --json databaseId -q '.[0].databaseId')"
gh release view v0.1.0 --json assets -q '.assets[].name'
```

**Expect:**
- the `build` jobs for amd64 and arm64 pass, and `publish` passes;
- `attest` passes on a public repo, or shows as skipped on a private repo;
- the assets are two `.oci.tar` files, two `.sbom.cdx.json` files and `SHA256SUMS`.

Then remove the test release: `gh release delete v0.1.0 --yes --cleanup-tag`. This is reversible; you can tag again later.

---

## 9. Private template repo only: allow workflow access

Skip this step if the template repo is public.

GitHub: `python-project-template` → *Settings → Actions → General → Access* → **Accessible from repositories owned by the user 'lloydbrian'** → Save. Then re-run the `template-repo` PR checks: `gh run rerun --failed`.

---

## 10. Final release **[changes remote]**

Merge the reference-app PR (`gh pr merge --squash --delete-branch` in `$REF`). Then in `$TPL`:

```bash
cd "$TPL" && git switch -c chore/release-v2.0.0
sed -i '' 's/^  default: v2.0.0-rc.1$/  default: v2.0.0/' copier.yml
python3 scripts/check_pins.py --release --tag v2.0.0
git commit -am "chore: release v2.0.0" && git push -u origin chore/release-v2.0.0
gh pr create --base main --fill
sleep 20 && gh pr checks --watch          # checks need a moment to register
gh pr merge --squash --delete-branch
git switch main && git pull
git tag v2.0.0 && git push origin v2.0.0
sleep 15
gh run watch "$(gh run list --workflow release.yml --branch v2.0.0 --limit 1 --json databaseId -q '.[0].databaseId')"
```

**Post-flight (prove the release by its artifact):**

```bash
gh release view v2.0.0 --json tagName,isPrerelease        # isPrerelease: false
git show v2.0.0:copier.yml | grep -A3 '^template_ref:'    # default: v2.0.0
git show v2.0.0:copier.yml | grep -c 'sha256:PENDING'     # 1 (the comment only)
cd "$REF" && git switch -c chore/template-v2.0.0 && copier update --vcs-ref v2.0.0 --skip-answered && git diff --stat
```

**Expect:** the reference app's update diff replaces `v2.0.0-rc.1` with `v2.0.0`, and nothing else, in `.copier-answers.yml`, `.github/workflows/ci.yml` and `release.yml`, `.mise.toml` (header comment), `README.md` and `CHANGELOG.md`. Commit it, open a PR and merge it once `check / check` passes.

---

## Rollback

| What | How | Notes |
|---|---|---|
| Template release | `gh release delete vX --yes`, `git push origin :refs/tags/vX` | Projects already on that tag keep working until the tag is deleted. Prefer releasing a fix (v2.0.1) over deleting a used tag |
| Repo rename | `gh repo rename template-repo-files -R $OWNER/python-project-template --yes` | Generated projects reference the new name; renaming back breaks their `uses:` unless GitHub's redirect applies |
| Reference app | `git revert` the merge commit in `template-repo` | v1 files return |
| v2 merge in template | `git revert -m 1 <merge>` | Do this before any project has generated from v2 |

**Do not roll back** the `.gitignore` hardening or the base-image pins. Those changes reduce risk on their own.

## Release log entry

After step 10, append to `docs/RELEASES.md`:

```text
2026-11-xx  v2.0.0  <commit>  lead time: <first commit → tag>  fix-forward/rollback: none  gates: 5/5 variants, 19/19 controls, update PASS
```
