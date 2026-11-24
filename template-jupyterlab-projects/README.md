# JupyterLab + VS Code Hybrid Template (Python 3.14, Podman)

A portable, per-repo setup for **JupyterLab-first exploration** with **VS Code for engineering** (`src/`, tests, packaging, git, CI). Same toolchain as the Python template: mise + uv + ruff + mypy + pytest + pre-commit, plus notebook hygiene (nbstripout, nbQA).

> **Multi-root workspaces:** each repo keeps its own `.venv` and `.vscode/settings.json`, so the interpreter never "flips" on restart.

## Set-up (once per machine)

### 1. Homebrew packages
```bash
brew update && brew upgrade && brew cleanup -s && brew doctor
brew install mise uv pre-commit git gh podman podman-compose trivy
brew install ripgrep fd fzf jq bat tree coreutils gnu-sed
brew install openssl readline zlib sqlite
brew install --cask visual-studio-code --appdir=~/Applications
echo 'eval "$(mise activate zsh)"' >> ~/.zshrc && source ~/.zshrc
```

| Tool | Why |
|---|---|
| `mise` | Pins the Python version per repo and runs every quality gate as a task |
| `uv` | Fast replacement for pip, venv, pipx and poetry: environments, resolution, lockfile |
| `pre-commit` | Runs format, lint and secret checks before every commit |
| `podman` + `podman-compose` | Rootless, daemonless containers with a Docker-compatible CLI |
| `trivy` | Scans container images and dependencies for known vulnerabilities |
| `gh` | GitHub from the terminal: clone, PRs, CI status |
| `rg`, `fd`, `fzf`, `jq`, `bat`, `tree` | Search code, find files, fuzzy-pick, filter JSON, read files, view folders |

### 2. Podman machine (macOS runs containers in a small Linux VM)
```bash
podman machine init && podman machine start     # once; afterwards `podman machine start` after a reboot
podman info --format '{{.Host.Security.Rootless}}'   # true = rootless
```
Optional: `brew install --cask podman-desktop` for a GUI. For VS Code Dev Containers, add to your **user** settings: `"dev.containers.dockerPath": "podman"`.

### 3. Terminal (optional)
```bash
brew install zsh-autosuggestions zsh-syntax-highlighting starship
brew install --cask font-jetbrains-mono-nerd-font iterm2 --appdir=~/Applications
cp ../template-terminal/starship.toml ~/.config/starship.toml
cat ../template-terminal/starship_zsh_integration.zsh >> ~/.zshrc && source ~/.zshrc
```
Set the terminal font to **JetBrainsMono Nerd Font** (Terminal.app: Settings > Profiles > Font; iTerm2: Profiles > Text).

### 4. VS Code extensions
Python, Pylance, Python Debugger, Ruff, Jupyter, Dev Containers, Even Better TOML. Optional: GitHub Copilot Chat, GitHub Theme. For Java in the same workspace: Extension Pack for Java, Debugger for Java.

Notebook extras (optional): `brew install pandoc graphviz`.

## Initialization (once per project)

1. **Create the repo and copy the template**:
   ```bash
   mkdir my-jupyter-ai-project && cd my-jupyter-ai-project && git init
   cp -R ../template-repo-files/template-jupyterlab-projects/. .
   mkdir -p data docs
   ```
2. **Rename** `jupyter-ai-labs` / `labs` in `pyproject.toml`, `src/labs/`, `tests/` and the kernel name in `.mise.toml`.
3. **Pin Python and bootstrap**: `mise trust && mise install && mise run bootstrap`
4. **Register the kernel** (JupyterLab and VS Code then use the same environment): `mise run kernel`
5. **Environment files**: `cp .env.example .env.dev`
6. **Check and commit**: `mise run ci && git add -A && git commit -m "chore: initial scaffold"`

## Day to day
```bash
mise run lab                 # JupyterLab with this repo's environment
uv run jupyter lab --ip 0.0.0.0 --port 8888 --no-browser    # inside a container
```
- Pick the **Python (jupyter-ai-labs)** kernel.
- Keep reusable logic in `src/labs/` with tests; notebooks import it (`%load_ext autoreload`, `%autoreload 2`).
- Before sharing: *Restart Kernel and Run All Cells*.
- Outputs are stripped on commit (nbstripout) and notebook code is linted (nbQA + ruff).
- Keep `data/` out of git (ignored) and never paste keys or personal data into cells.

## Tasks

| Task | What it does |
|---|---|
| `mise run bootstrap` | Create `.venv`, lock if needed, install deps and pre-commit hooks (once per clone) |
| `mise run format` | Format with ruff |
| `mise run lint` | Lint with ruff (fails on issues) |
| `mise run type` | Type-check with mypy (strict) |
| `mise run test` | Tests with coverage (fails under 80%) |
| `mise run security` | `pip-audit` + `bandit` (fails on findings) |
| `mise run image` | Build the production image with Podman |
| `mise run scan` | Scan the image with trivy (fails on HIGH/CRITICAL) |
| `mise run lab` | Start JupyterLab |\n| `mise run kernel` | Register this repo's Jupyter kernel |\n| `mise run ci` | Exactly what CI runs: locked sync, all hooks, types, tests |

## Layout

```text
.
├── .container/            Containerfile (dev/test/prod) + compose.yaml
├── .devcontainer/         VS Code dev container (Podman)
├── .github/workflows/     ci.yml runs `mise run ci`
├── .vscode/settings.json  per-repo interpreter pin + format on save
├── .containerignore  .env.example  .gitignore  .pre-commit-config.yaml
├── .mise.toml             Python 3.14 pin, env, tasks
├── pyproject.toml  uv.lock  README.md
├── src/labs/
│   └── helpers.py         tested helpers notebooks import
├── notebooks/             exploration only
├── data/                  local data (git-ignored)
├── docs/
└── tests/
```

## Environment files and secrets

- `.env.example` is committed and lists variable **names** only.
- Copy it to `.env.dev`, `.env.test` or `.env.prod` and fill values locally. All `.env*` files except the example are git-ignored.
- `APP_ENV` picks the file at startup; real environment variables always win over file values.
- Production values belong in the platform's secret store (or `podman secret`), not in files.

## Containers (Podman)

One multi-stage `.container/Containerfile` with three targets:

| Target | Use |
|---|---|
| `dev` | Tooling included; your source is bind-mounted over `/app` |
| `test` | Copies `tests/` and runs them: the build fails if tests fail |
| `prod` | Runtime only, non-root |

```bash
podman build -f .container/Containerfile --target test .
podman build -f .container/Containerfile --target prod -t jupyter-ai-labs:0.1.0 .
mise run scan
podman compose -f .container/compose.yaml up      # JupyterLab on 127.0.0.1:8888; keep token auth on
```

Secrets go in at run time, never into the image:
```bash
printf '%s' "$SOME_API_KEY" | podman secret create some_api_key -
podman run --secret some_api_key,type=env,target=SOME_API_KEY ...
```

The virtual environment inside images lives at `/opt/venv` (`UV_PROJECT_ENVIRONMENT`), so a mounted source folder never hides or clashes with it. Rootless notes: use host ports of 1024 or higher; add `:Z` to bind mounts on SELinux hosts.

## What changed in this alignment (and why)

| Before | Problem | Now |
|---|---|---|
| `.gitignore` covered `.env` only | `.env.dev`, `.env.test`, `.env.prod` could be committed | `.env.*` ignored, `.env.example` committed |
| Dev tools in `[project.optional-dependencies].dev` | `uv sync --dev` did not install them | `[dependency-groups]`: plain `uv sync` installs `dev` |
| Python 3.14 (mise), 3.12 (Docker), 3.11 (ruff, mypy, requires-python) | Passing locally, failing in the container, or the reverse | 3.14 everywhere |
| Entry point and mypy targeted a missing `ai_agent` package | Broken CLI and type check | Real package name everywhere |
| `pip-audit \|\| true` | Security task could never fail | Fails on findings; CI-ready |
| Docker files in `.docker/` | Team moved to Podman | `.container/Containerfile` (dev/test/prod) + `compose.yaml` |
| Duplicate `.mise.toml` / `.mise-python.toml` | Two sources of truth | `.mise.toml` only (Node and Java variants kept for polyglot repos) |
| No tests, CI, `.env.example`, `.containerignore` | Gates promised but not wired | All present and passing |
