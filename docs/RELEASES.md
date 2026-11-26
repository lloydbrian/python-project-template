# Release log

One line per template release: date, tag, commit, lead time (first commit → tag), whether a fix-forward or rollback was needed, gate totals.

| Date | Tag | Commit | Lead time | Fix-forward / rollback | Gates |
|---|---|---|---|---|---|
| 2026-11-25 | v2.0.0 | `8e4d1a6` | 44 h 22 min (`df75525` 2026-11-24 02:59 UTC → tag push 2026-11-25 23:21 UTC) | 2 fix-forwards, no rollback: rc.2 (blank env values fall back to defaults), rc.3 (release scan reads the unpacked OCI layout) | template-ci 8/8 variants, 24/24 negative controls, update PASS; PR #5 11/11 checks; release run 45720703997 success |

## v2.0.0 evidence

- **Pre-releases:** `v2.0.0-rc.1` (`9baafb4`), `v2.0.0-rc.2` (`dd26318`), `v2.0.0-rc.3` (`0fdf540`).
- **Release:** run 45720703997 (verify, template-ci, publish) succeeded; full release published 2026-11-25 23:25 UTC and marked latest.
- **End-to-end release path:** the reference app `lloydbrian/template-repo` cut a test release `v0.1.0` at `d3ef920` on rc.3 (run 45543584065, 4/4 jobs). All 4 attestations verified with `--signer-workflow lloydbrian/python-project-template/.github/workflows/python-release.yml`; a wrong signer was rejected. The test release was then removed. Asset digests:
  - `template-sample-app-0.1.0-linux-amd64.oci.tar`: `sha256:1c5f4fbd430b8f0b89f1e3d077890f9551715ca20e0fbcc9e33be5dd495c0687`
  - `template-sample-app-0.1.0-linux-arm64.oci.tar`: `sha256:15a7842065c4a0627fcc8a9839403f2370540e981b5a4d13ca0c6cbf9e25196a`
  - `template-sample-app-0.1.0-linux-amd64.sbom.cdx.json`: `sha256:7bcb99759aa2afe8b53ccdd10c39935381f7c0b68142e8aa450e9e7b2e182e9e`
  - `template-sample-app-0.1.0-linux-arm64.sbom.cdx.json`: `sha256:8159377ea8bf0516273757c823f65a96ef24a8ca1337a29c32d83adf15675ea3`
- **Reference app on the final tag:** `template-repo` PR #3 merged as `13fdf39`; `check / check` green; local gates (ci, image, scan, smoke) passed after a no-cache rebuild picked up the libzstd1 fix (CVE-2026-124851).
