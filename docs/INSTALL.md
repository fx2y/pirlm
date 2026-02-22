# PIRML Installation & Distribution

## 1. Node/TS Toolchain
PIRML requires Node 24 and TypeScript 5. Versions are pinned in `.mise.toml` and `package-lock.json`.

```sh
# Install dependencies
npm install
```

## 2. pi Extension Installation

### Global Install
```sh
pi install git+https://github.com/mariozechner/pirlm.git
```

### Project-local Install
```sh
# In your project root
mkdir -p .pi/extensions
git clone https://github.com/mariozechner/pirlm.git .pi/extensions/pirml
# Then tell pi to reload
# /reload
```

### Manual Configuration
You can explicitly link the extension in your `.pi/settings.json`:
```json
{
  "extensions": ["/absolute/path/to/pirlm/.pi/extensions/pirml"]
}
```

## 3. Path Precedence
`pi` discovery order:
1. Project-local: `.pi/extensions/` (Highest precedence)
2. Global: `~/.pi/agent/extensions/`

Use `/reload` to pick up changes in local extensions without restarting the agent.

## 4. Verification
After installation/reload:
1. Run `/pirml` to verify the command is registered.
2. Run `/pirml run tests/prog_ok.py` to verify the Python runtime bridge.
3. Check the TUI for a `CustomEntry` pointer and a summary `CustomMessage`.
