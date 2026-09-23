# Setting up a new machine

The goal is Claude Code running with no permission prompts, the Vercel, Supabase, Fly and GitHub CLIs installed and logged in so Claude can do everything from the terminal, and this repo's hooks and skills installed. It takes about 30 minutes. The commands are for Ubuntu/Debian.

**The easy way:** do steps 1–2 yourself, clone this repo, start `claude` inside it, and paste:

> Walk me through setting up my machine for coding, one step at a time, following docs/SETUP.md in this repo. Check what's already installed first. For each token, tell me exactly which page to open and what to click, then wait while I paste it in. Store tokens only in `~/.config/dev-secrets.env`, never in a repo. At the end, run every "check it worked" command and tell me what passed.

## 1. Node (via nvm)

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/master/install.sh | bash
# close and reopen the terminal, then:
nvm install --lts
node --version
```

## 2. Claude Code, always without permission prompts

```bash
npm install -g @anthropic-ai/claude-code
echo "alias claude='claude --dangerously-skip-permissions'" >> ~/.bashrc
source ~/.bashrc
claude          # log in with your Anthropic account the first time
```

This repo's `settings.json` also sets `"permissions": {"defaultMode": "bypassPermissions"}` and `"skipDangerousModePermissionPrompt": true`, so you don't get the warning on every start.

What this means: Claude runs any command without asking, including installs, deploys and deletes. The trade is deliberate. The guard hooks, the beta/stable deploy channels and the backups are what keep it safe. Don't do this on a machine holding things you can't lose and haven't backed up.

## 3. Get the tokens (the only dashboard step)

Each token is a password for its service. Create it and paste it straight into the secrets file in step 5. Never put it in a repo, a chat message or a screenshot.

| Service | Where to get it | Name it |
| --- | --- | --- |
| Vercel | vercel.com → avatar → **Account Settings → Tokens** → Create (scope: your team; no expiry or 1 year) | `VERCEL_TOKEN` |
| Supabase | supabase.com/dashboard → avatar → **Account → Access Tokens** → Generate new token | `SUPABASE_ACCESS_TOKEN` |
| Fly.io | fly.io/dashboard → **Account → Access Tokens**, or after installing flyctl run `fly tokens create org` | `FLY_API_TOKEN` |
| GitHub | No token needed: `gh auth login` logs in through the browser (step 6) | — |

## 4. Install the CLIs

```bash
# Vercel
npm install -g vercel

# Supabase (it doesn't support a global npm install, so use the release binary)
curl -sL https://github.com/supabase/cli/releases/latest/download/supabase_linux_amd64.tar.gz | tar xz supabase
sudo mv supabase /usr/local/bin/

# Fly.io
curl -L https://fly.io/install.sh | sh
echo 'export PATH="$HOME/.fly/bin:$PATH"' >> ~/.bashrc

# GitHub
sudo apt install gh
```

Try without `sudo` first. Only the Supabase move and `apt` need it.

## 5. Store the tokens once

```bash
mkdir -p ~/.config && touch ~/.config/dev-secrets.env && chmod 600 ~/.config/dev-secrets.env
nano ~/.config/dev-secrets.env
```

Put in:

```bash
export VERCEL_TOKEN=paste-here
export SUPABASE_ACCESS_TOKEN=paste-here
export FLY_API_TOKEN=paste-here
```

Then load it in every terminal:

```bash
echo '[ -f ~/.config/dev-secrets.env ] && source ~/.config/dev-secrets.env' >> ~/.bashrc
source ~/.bashrc
```

All three CLIs read these variables automatically. The env var is the most reliable path: flyctl, for one, has failed to read a token from its own config file.

## 6. Log in and check it worked

```bash
vercel whoami                                   # prints your Vercel username
supabase login --token "$SUPABASE_ACCESS_TOKEN" --no-browser
supabase projects list                          # lists your Supabase projects
fly auth whoami                                 # prints your Fly email
gh auth login                                   # pick GitHub.com, HTTPS, browser login
gh auth status
```

Each should print your account, not an error. Then link each project from inside its folder with `vercel link` and `supabase link --project-ref <ref>`.

## 7. Install this workflow

```bash
git clone https://github.com/AkiraTheSquid/claude-code-workflow.git ~/Applications/claude-code-workflow
cd ~/Applications/claude-code-workflow
./install.sh --dry-run
./install.sh
```

Then:

1. **Modulario hooks:** `~/Applications/Modulario/setup/install.sh`. It wires Modulario's PreToolUse, PostToolUse and Stop hooks and asks which project to watch.
2. **Agent budget:** `mod agents` shows it; `mod agents set 0` blocks every subagent spawn (the value lives in Modulario's `configs/stopgate.json`, key `max_agents`).
3. **collab, per shared repo:** `python3 ~/.local/share/agent-collab/install-hooks.py <repo>`. Only needed where you run more than one Claude session at a time.
4. **Plugins,** inside Claude Code:
   ```
   /plugin marketplace add JuliusBrussee/caveman
   /plugin install caveman@caveman
   /plugin marketplace add typesafe-ai/skills
   /plugin install frontend-design@claude-plugins-official
   ```
5. **graphify:** `uv tool install graphifyy && graphify install` (or use `pipx`).
6. **Codex for `/critic`:** `npm install -g @openai/codex && codex login`. Pin the reviewer model and effort in `~/.codex/config.toml` and in Modulario's `run_critic.py`. The effort level once dropped silently from `xhigh` to `medium`.
7. **Playwright for browser checks** (in a scratch venv, no browser download needed):
   ```bash
   python3 -m venv ~/pw && ~/pw/bin/pip install playwright
   chrome_dev http://localhost:3000     # headless debug Chrome on :9222
   ```
   Connect with `chromium.connect_over_cdp("http://127.0.0.1:9222")`.
8. Make sure `~/.local/bin` is on your `PATH`, then start a **new** Claude session. Hooks load at session start.

## 8. Merge your own settings

If you already had a `~/.claude/CLAUDE.md` or `settings.json`, the installer wrote `CLAUDE.workflow.md` and `settings.workflow.json` beside them. Ask Claude to merge them: "merge settings.workflow.json into settings.json, keeping my existing hooks".
