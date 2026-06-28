# Gemini Web Agent

**Drive Gemini Web (gemini.google.com) via Chrome CDP — no API key needed, free Pro Extended Thinking.**

Use DeepSeek/Claude/Hermes for planning, Gemini Web for free deep reasoning. The perfect "thinker + executor" synergy.

## Why?

### 🧠 Free Deep Reasoning
Gemini Web is **free**. Pro Extended Thinking generates massive reasoning tokens at zero cost. Your planner (DeepSeek/Claude) only consumes a few planning tokens.

### 🌏 Works Behind GFW
Injected Chrome feature flags bypass Google's Safe Browsing / Optimization Guide dependency chain that blocks navigation in restricted networks.

### 🎯 Multi-modal for Text-only LLMs
DeepSeek and other text-only models gain screenshot analysis, web browsing, and UI interaction through the CDP bridge.

## Features

- ✅ Launch Chrome with GFW bypass flags
- ✅ Navigate to Gemini Web automatically
- ✅ Switch to **Pro Extended Thinking** (deep reasoning mode)
- ✅ Send prompts and read responses via CLI
- ✅ Screenshot capture
- ✅ Session management (reuse tabs, don't lose context)
- ✅ Angular change detection workaround for long texts
- ✅ Single shared WebSocket connection (CDP page targets require this)
- ✅ Hermes Agent skill integration

## Quick Start

### Prerequisites

| Dependency | Install |
|-----------|---------|
| Python 3.8+ | System |
| Chrome | `C:\Program Files\Google\Chrome\Application\chrome.exe` |
| playwright (Python) | `pip install playwright` |
| websocket-client | `pip install websockets` |

### 1. Install

```bash
git clone https://github.com/YOUR_USER/gemini-web-agent.git
cd gemini-web-agent
pip install playwright websockets
python -m playwright install chromium  # optional, uses system Chrome by default
```

### 2. Configure Proxy (China only)

Edit the `PROXY` variable at the top of `gemini_agent.py`:

```python
PROXY = "socks5://127.0.0.1:10808"   # v2rayN
# PROXY = "http://127.0.0.1:7897"    # Clash
# PROXY = ""                          # No proxy (non-China)
```

Or set the environment variable:
```bash
export GEMINI_PROXY="socks5://127.0.0.1:10808"
```

### 3. Login to Google (one-time)

```bash
python -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        user_data_dir='$HOME/.chrome-cdp-profile',
        headless=False
    )
    ctx.pages[0].goto('https://gemini.google.com/u/0/app')
    input('Login in the browser window, then press Enter...')
    ctx.close()
"
```

Login persists in `~/.chrome-cdp-profile`.

### 4. Launch and Connect

```bash
# Start Chrome with CDP + GFW bypass
python gemini_agent.py launch

# Navigate to Gemini
python gemini_agent.py navigate

# Check status
python gemini_agent.py status
```

### 5. Use It

```bash
# Send a prompt
python gemini_agent.py send "Explain quantum entanglement in 3 sentences"

# Wait for response (8-15s for Extended mode)
# Read the response
python gemini_agent.py read

# Read full page content
python gemini_agent.py read --full
```

## CLI Reference

| Command | Description |
|---------|-------------|
| `launch` | Start Chrome with CDP + GFW bypass flags |
| `launch --kill` | Force restart Chrome |
| `navigate` | Open or refresh Gemini |
| `status` | Show current tab title and model mode |
| `pro-extended` | Switch to Pro Extended Thinking |
| `send "text"` | Send a prompt to Gemini |
| `read` | Read the latest Gemini response |
| `read --full` | Read full page text |
| `screenshot [path]` | Capture screenshot |
| `list` | List all Chrome tabs |
| `close` | Close Gemini tab |

## Hermes Agent Integration

This project is packaged as a **Hermes Agent skill**. If you use Hermes:

1. Copy the `skills/gemini-web-agent/` directory to your Hermes skills folder
2. The `SKILL.md` file defines trigger conditions and workflow
3. When you say "use Gemini for deep thinking" in a Hermes session, it auto-loads

```bash
# Copy to Hermes skills
cp -r gemini-web-agent/skills/gemini-web-agent ~/AppData/Local/hermes/skills/software-development/
```

## How It Works

```
Your Agent (DeepSeek/Claude/Hermes)
        │  plan prompt
        ▼
  Chrome CDP (WebSocket :9222)
        │  inject prompt
        ▼
  Gemini Web (gemini.google.com)
        │  free deep reasoning
        ▼
  Read response
```

### Why Shared WebSocket?

CDP page targets only respond on the **first WebSocket connection** opened to them. Each subsequent connection receives one empty event then hangs. This tool uses a singleton `CDPClient` that opens one connection and reuses it for all commands.

### GFW Bypass Flags

```bash
--disable-features=OptimizationHints,Translate,HttpsUpgrades
--disable-background-networking
--disable-client-side-phishing-detection
--disable-field-trial-config
--disable-component-update
--proxy-server=socks5://127.0.0.1:10808  # user-configured
```

Without these flags, Chrome's security components (Safe Browsing, Optimization Guide) fail to reach Google's cloud in restricted networks, triggering a **fail-safe** that blocks all navigation (symptom: `about:blank`).

## Pro Extended Mode

```python
# Menu layout (Gemini v3.x, Traditional Chinese)
index 0: "3.1 Flash-Lite"           # Fast, basic
index 1: "3.5 Flash"                # Default
index 2: "3.1 Pro"                  # Advanced math & code
index 3: "思考等级 / Thinking Level" # Expand thinking submenu
  index 4: "标准 / Standard"
  index 5: "扩展 / Extended"         # Deep reasoning ← THIS
```

Run: `python gemini_agent.py pro-extended`

## Angular Change Detection Workaround

Gemini's input is a Quill.js rich-text editor with Angular zone.js. Long text (>5K chars) via `Input.insertText` may not trigger Angular change detection, leaving the send button disabled.

**Fix**: Type a space then delete it to trigger zone.js:
```python
await cdp.call("Input.insertText", {"text": " "})
await cdp.call("Input.deleteContentBackward", {})
# Then click send
```

This is handled automatically by `gemini_agent.py send`.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Gemini tab `about:blank` | GFW blocked Chrome security init | `launch --kill` with all bypass flags |
| `ERR_BLOCKED_BY_CLIENT` | Safe Browsing triggered | Ensure `--disable-features=OptimizationHints` is set |
| SSL handshake failure | VLESS Reality vs Chrome BoringSSL conflict | Use HTTP/SOCKS5 proxy, **not** VLESS |
| Send button not appearing | Angular change detection missed | Use the space+delete trigger (auto-handled) |
| Status returns "unknown" | WebSocket connection stale | Run `navigate` first, or `launch --kill` |
| Timeout on CDP calls | Multiple WebSocket connections to same target | `gemini_agent.py` uses a shared connection — always use the script |

## File Structure

```
gemini-web-agent/
├── README.md                          # This file
├── gemini_agent.py                    # Main CLI script (standalone)
├── SKILL.md                           # Hermes Agent skill format
├── scripts/
│   └── gemini_agent.py                # Copy for Hermes skill dir
└── references/
    └── test-session-2026-06-28.md     # Test records & discoveries
```

## License

MIT
