# Workstation set-up (macOS, once per machine)

Everything a developer needs before generating or cloning a project from **python-project-template**. Linux works the same way. Swap Homebrew for your package manager and skip the `podman machine` step (Linux runs containers natively).

**Containers use Podman, not Docker.** Nothing here installs or needs Docker Desktop.

## 1. Homebrew packages

```bash
brew update && brew upgrade && brew cleanup -s && brew doctor
brew install mise uv git gh podman podman-compose
brew install ripgrep fd fzf jq bat tree coreutils gnu-sed        # optional, but used in our docs
brew install skopeo                                              # template maintainers only: `mise run pin-images`
brew install --cask visual-studio-code --appdir=~/Applications
echo 'eval "$(mise activate zsh)"' >> ~/.zshrc && source ~/.zshrc
uv tool install copier                                           # generates and updates projects
```

| Tool | Why it is here |
|---|---|
| `mise` | Installs the exact Python and CLI tool versions each repo pins in its `.mise.toml`, and runs every quality gate as a named task (`mise run ci`). Replaces pyenv, Make and per-tool installers |
| `uv` | Python package and environment manager: venvs, resolution, the `uv.lock` lockfile, and `uv tool` for CLIs such as Copier. Each repo also pins its own uv through mise |
| `copier` | Generates a new project from the template and later replays template updates onto it (`copier update`) |
| `git`, `gh` | Version control; GitHub from the terminal (clone, PRs, CI status, releases) |
| `podman` | Rootless, daemonless containers with a Docker-compatible CLI. The team standard |
| `podman-compose` | The provider that `podman compose` uses to run `compose.yaml` files |
| `rg`, `fd`, `fzf`, `jq`, `bat`, `tree` | Search code, find files, fuzzy-pick, filter JSON, read files with highlighting, view folder trees |
| `coreutils`, `gnu-sed` | GNU versions of `sed` and friends, so scripts behave the same on macOS and Linux |
| `skopeo` (maintainers) | Reads image manifests from registries without pulling, to pin base images by digest |

**Not installed globally, on purpose:**

- **Python.** mise installs the version each repo pins, so projects never depend on whatever Python the machine has.
- **pre-commit, ruff, mypy, pytest.** These are dev-group dependencies of each project, at that project's locked versions.
- **trivy, gitleaks.** Pinned per repo through mise or the pre-commit config.

Earlier versions of this guide installed `openssl readline zlib sqlite` so pyenv could compile Python. mise installs prebuilt Python, so they are no longer needed.

## 2. Podman machine

macOS runs Linux containers inside a small VM managed by `podman machine`.

```bash
podman machine init --cpus 4 --memory 8192 --disk-size 60   # once; size it for your builds
podman machine start                                         # after every reboot
podman info --format '{{.Host.Security.Rootless}}'           # true = rootless
podman run --rm docker.io/library/hello-world                # end-to-end check
```

- **Rootless** is the default and what the templates assume. Containers run as your user, and host ports must be 1024 or higher.
- **Apple silicon** builds `linux/arm64` images natively. CI builds `linux/amd64` and `linux/arm64` on native runners, so you rarely need `--platform`. Emulated amd64 builds work but are slow.
- Optional GUI: `brew install --cask podman-desktop`.
- After a macOS upgrade, if Podman cannot connect: `podman machine stop && podman machine start`.

## 3. VS Code

Extensions: **Python**, **Pylance**, **Python Debugger**, **Ruff**, **Jupyter**, **Dev Containers**, **Even Better TOML**. Optional: GitHub Copilot Chat, GitHub Theme. For Java in the same workspace: Extension Pack for Java, Debugger for Java.

Add to your **user** settings (`Cmd+Shift+P` → *Preferences: Open User Settings (JSON)*) so Dev Containers use Podman:

```json
"dev.containers.dockerPath": "podman"
```

Each generated repo ships its own `.vscode/settings.json` pinning the interpreter to that repo's `.venv`. Multi-root workspaces therefore keep the right environment per folder.

## 4. Git identity and global ignore

```bash
git config --global user.name  "Your Name"
git config --global user.email "you@example.com"
git config --global init.defaultBranch main
git config --global pull.rebase true
```

A global ignore file keeps editor and OS clutter (`.DS_Store`, `.idea/`) out of every repo without each project listing it. If you have not set one up, use the hardened block from the template's `.gitignore` as a starting point:

```bash
git config --global core.excludesFile ~/.config/git/ignore
```

## 5. Terminal (optional)

```bash
brew install zsh-autosuggestions zsh-syntax-highlighting starship
brew install --cask font-jetbrains-mono-nerd-font iterm2 --appdir=~/Applications
gh repo clone lloydbrian/python-project-template ~/Developer/repositories/python-project-template
cd ~/Developer/repositories/python-project-template
mkdir -p ~/.config
cp workstation/terminal/starship.toml ~/.config/starship.toml          # or starship-custom.toml
cat workstation/terminal/starship_zsh_integration.zsh >> ~/.zshrc
cat >> ~/.zshrc <<'ZSH'
source "$(brew --prefix)/share/zsh-autosuggestions/zsh-autosuggestions.zsh"
source "$(brew --prefix)/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh"   # keep last
ZSH
source ~/.zshrc
```

Set the terminal font to **JetBrainsMono Nerd Font** (Terminal.app: *Settings → Profiles → Font*; iTerm2: *Profiles → Text*). The Starship prompt shows the active Python and virtual environment and the git branch, which helps catch "wrong interpreter" mistakes early.

## 6. Verify

```bash
mise --version && uv --version && copier --version && podman --version
podman machine list            # one machine, "Currently running"
```

Then generate a project. See the template's main `README.md`.

## Secrets on this machine

Never paste tokens into files that might be committed, or into chat tools. Declare them into a shell variable when needed and unset them afterwards:

```bash
read -rs GH_TOKEN && export GH_TOKEN      # hidden input, not stored in shell history
# ... use it ...
unset GH_TOKEN
```

Prefer `gh auth login` (stores the token in the macOS keychain) over a token in an environment variable.
