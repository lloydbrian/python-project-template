# Design choices: Podman, no registry, and tags that never move

Three decisions shape this template more than any tool choice: containers run on **rootless Podman**, releases ship as **files instead of registry images**, and a **published release tag can never change**. Each one removes a class of failure, and each one has a cost. This page explains both, with the evidence from the v2.0.0 and v2.0.1 releases. The binding records are the ADRs: [0003](adr/0003-podman-only.md), [0011](adr/0011-release-artifacts-without-registry.md) and [0007](adr/0007-supply-chain-pinning.md).

**Audience:** anyone deciding whether to adopt the template, or reviewing why it works the way it does. For day-to-day use, start with the [README](../README.md#quick-start).

## Rootless Podman

**The problem.** A classic Docker Engine set-up runs one long-lived daemon as root, and every `docker` command talks to it through a socket. Anyone who can reach that socket can start a privileged container and own the machine. A container escape lands as root.

**The choice.** Podman runs each container as a child process of the user who started it. There is no daemon and no root socket. By default it runs rootless: uid 0 inside the container maps to the developer's own unprivileged user on the host. Its CLI matches Docker's (`podman build`, `podman run`, `podman compose`), and it builds the same OCI images.

**What it costs.**

- On macOS, containers run inside a small Linux VM (`podman machine`), which must be started after each reboot.
- Rootless containers cannot bind host ports below 1024, so the template's `http_port` must be 1024 or higher.
- Some third-party tools assume a Docker socket. Podman can expose a compatible socket, but the template does not rely on it.

### How Podman compares

| | Podman | Docker Engine | Docker Desktop | containerd + nerdctl | Kubernetes |
|---|---|---|---|---|---|
| **What it is** | Container engine and CLI | Container engine (daemon) and CLI | Desktop app bundling Docker Engine in a VM | Low-level runtime plus a Docker-style CLI | Orchestrator that runs containers across machines |
| **Daemon** | None | `dockerd`, long-lived | Inside its VM | `containerd`, long-lived | Kubelet on each node, with a runtime such as containerd or CRI-O |
| **Rootless** | Default | Optional mode | The engine runs as root inside its VM, isolated from the host | Supported | Per-pod security settings |
| **Builds images** | Yes (`podman build`, Buildah inside) | Yes (BuildKit) | Yes (BuildKit) | Yes (with BuildKit) | No: it runs images built elsewhere |
| **Runs compose files** | `podman compose` | `docker compose` | `docker compose` | `nerdctl compose` | No: uses its own manifests |
| **Licence** | Apache-2.0 | Apache-2.0 | Free for personal use, education and small businesses; larger companies need a paid subscription (check Docker's current terms) | Apache-2.0 | Apache-2.0 |
| **Best fit** | Rootless local development and single hosts | Teams already standardised on Docker | Docker on macOS or Windows with a GUI | Kubernetes nodes, and people who want its runtime locally | Running many services with scaling and self-healing |

The template standardises on one engine on purpose. Every command in the docs, every task and every CI step is tested against Podman. Supporting two engines would double that surface, and the second would drift untested.

### Moving to Docker or Kubernetes

**Disclaimer:** the template supports and tests Podman only. Moving a generated project to Docker or Kubernetes should be possible, because everything the template builds is a standard OCI image, described by standard files. Template CI does not test these paths, so treat them as a starting point and run your own gates afterwards.

**To Docker.** The Containerfile is an ordinary Dockerfile with another name, and the compose file uses standard keys.

```bash
docker build -f .container/Containerfile --target prod -t ticket-triage:dev .
docker compose -f .container/compose.yaml up --build
```

Then adjust the Podman-specific parts:

- `.mise.toml` tasks call `podman`: change them to `docker`.
- The dev container passes `--userns=keep-id`, which only Podman understands: remove it and check the workspace mount options.
- Generated CI calls the template's shared workflows, which use Podman. A Docker pipeline means maintaining your own workflow.

**To Kubernetes.** Kubernetes pulls images from a registry, so the release archive has to be pushed to one first. Verify it, then copy it with [skopeo](https://github.com/containers/skopeo):

```bash
sha256sum -c SHA256SUMS
skopeo copy oci-archive:ticket-triage-0.1.0-linux-amd64.oci.tar docker://registry.example.invalid/ticket-triage:0.1.0
```

`podman kube generate <container>` turns a running container into a starting Pod manifest. Carry over the same protections the template's compose file and smoke test use:

- `runAsNonRoot: true` and `readOnlyRootFilesystem: true`;
- `allowPrivilegeEscalation: false` and all capabilities dropped;
- liveness and readiness probes on `/health/live` and `/health/ready`;
- secrets as Kubernetes Secrets, never baked into the image.

Reference the image by digest in the manifest, for the same reason the template pins base images by digest: a tag can move.

## No registry

**The problem.** A registry is another service to secure, pay for and authenticate to. Pushing from CI needs a write credential. An image tag in a registry can be overwritten, so "the image we tested" and "the image we run" can quietly differ.

**The choice.** A project release is a GitHub release with files attached:

- one OCI archive per architecture (amd64 and arm64, each built on a native runner);
- one CycloneDX SBOM per architecture;
- `SHA256SUMS`;
- on public repos, a build-provenance attestation for each archive and SBOM, signed by a job that runs no project code.

Anyone can check what they received before running it: `sha256sum -c SHA256SUMS`, then `gh attestation verify` with the template's release workflow as the signer.

**What it costs.**

- Running on Kubernetes or any registry-based platform needs an extra push step (above).
- Archives are downloaded whole: there is no layer sharing between versions.
- Attestations need a public repo, or a private repo on GitHub Enterprise Cloud.

## Tags that never move

**The problem.** Generated projects call the template's shared CI and release workflows by tag (`python-ci.yml@v2.0.1`), because Copier can only render a tag, not a commit. If that tag could be moved, someone could point it at different code, and every project's CI would run it without any change in the project.

**The choice.** A repository ruleset blocks updating or deleting any `v*` tag, with no bypass for anyone, including the owner. A published release always means the same code. Actions and pre-commit hooks are pinned by commit SHA, and base images by digest, for the same reason.

**What it costs.** A bad release cannot be fixed in place. The fix is always the next tag. The v2.0.0 release shows this working:

- `v2.0.0-rc.1` crashed a real project that had blank values in its old `.env.dev`. The fix shipped as `rc.2`.
- `rc.2`'s release scan failed on a real test release. The fix shipped as `rc.3`.
- `v2.0.0` was tagged once both fixes were proven. The old candidates still point at exactly what they always did.

v2.0.1 needed no fix-forward: its release path is now tested on every pull request by a release dry run on both architectures. See the [release log](RELEASES.md).

## Decisions behind this page

| Choice | ADR |
|---|---|
| Podman only | [0003](adr/0003-podman-only.md) |
| Pin by digest and SHA | [0007](adr/0007-supply-chain-pinning.md) |
| Reusable, versioned CI | [0009](adr/0009-reusable-ci-workflow.md) |
| Release files, no registry | [0011](adr/0011-release-artifacts-without-registry.md) |
