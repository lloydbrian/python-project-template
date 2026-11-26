# Records docs/demo/quickstart.gif with VHS (https://github.com/charmbracelet/vhs).
# Run from the repo root on a machine set up per workstation/README.md:  vhs docs/demo/quickstart.tape
# It generates a real project in a temporary folder (never inside this repo) and runs every gate,
# so the recording is the actual run, not a mock. Re-record after each release (update the tag below).
# The GIF is written outside the repo and hosted as a GitHub attachment, not committed: a readable
# recording is several times the 500 KB large-file limit, and re-recordings would grow git history.

Output "/tmp/quickstart.gif"
Require copier
Require mise
Require git

Set Shell zsh
Set FontSize 15
Set Width 1100
Set Height 620
Set Padding 16
Set Framerate 12
Set TypingSpeed 35ms
Set PlaybackSpeed 2

# Set-up the viewer does not need to see: an empty temp folder and a plain prompt VHS can wait on.
Hide
Type "cd $(mktemp -d /tmp/quickstart.XXXXXX) && PROMPT='> ' && RPROMPT='' && SECONDS=0 && clear" Enter
Show

Type "copier copy --vcs-ref v2.0.1 --defaults --data project_name='Ticket Triage' gh:lloydbrian/python-project-template ticket-triage" Enter
Wait@3m
Type "cd ticket-triage && git init -q -b main && mise trust -q && mise install -q && mise run bootstrap" Enter
Wait@10m
Type `git add -A && git commit -qm 'chore: scaffold from python-project-template v2.0.1' && mise run ci && echo "all gates passed in ${SECONDS}s of real time (this recording plays at 2x)"` Enter
Wait@10m
Sleep 4s
