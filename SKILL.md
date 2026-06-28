---
name: gemini-web-agent
description: >-
  Drive Google Gemini Web (gemini.google.com) via Chrome CDP — launch browser
  with GFW bypass, switch to Pro Extended Thinking, send prompts, read responses,
  manage conversation sessions. Designed for Chinese network environment.
trigger: >-
  User asks to use Gemini for deep reasoning, or says 'run this through Gemini',
  'use Gemini Web', 'send to Gemini for extended thinking', 'Gemini 深度思考',
  or references AgentChat / Gemini Web automation.
  Does NOT apply to Gemini API calls — this is purely Web/CDP-based.
---

# Gemini Web Agent via CDP

Drive **Gemini Web** (gemini.google.com) programmatically via Chrome CDP on Windows. Works behind the GFW by injecting bypass flags. No API key needed — Gemini Web is free.

## Prerequisites

- **Unified tool (recommended)**: `C:\Users\Administrator\gemini_agent.py` — one script for launch, navigate, model switching, send, read, screenshot. Auto-installs missing deps.
- Fallback: `C:\Users\Administrator\chrome_cdp.py` (see `local-chrome-control` skill)
- GFW launch script: `C:\Users\Administrator\launch_gemini_chrome.py`
- Python packages: `websockets`, `requests` (auto-installed by `gemini_agent.py`)
- SOCKS5 proxy running (v2rayN on `127.0.0.1:10808`)
- Google account logged in once (persists in `~/.chrome-cdp-profile`)

Refer to the `local-chrome-control` skill for generic CDP operations.

## Quick Start (gemini_agent.py)

The `gemini_agent.py` script wraps the entire Gemini Web workflow into single commands:

```bash
# Set proxy (default: socks5://127.0.0.1:10808, override via env var)
export GEMINI_PROXY="socks5://127.0.0.1:10808"

# 1. Launch Chrome (GFW bypass + CDP 9222)
python /c/Users/Administrator/gemini_agent.py launch

# 2. Navigate to Gemini
python /c/Users/Administrator/gemini_agent.py navigate

# 3. Check current model
python /c/Users/Administrator/gemini_agent.py status

# 4. Switch to Pro Extended (for deep reasoning)
python /c/Users/Administrator/gemini_agent.py pro-extended

# 5. Send a prompt
python /c/Users/Administrator/gemini_agent.py send "用三句话解释..."

# 6. Read the response
sleep 12
python /c/Users/Administrator/gemini_agent.py read

# 7. Continue the same conversation
python /c/Users/Administrator/gemini_agent.py send "继续深入解释..."
sleep 12
python /c/Users/Administrator/gemini_agent.py read
```

### Command reference

| Command | Description |
|---------|-------------|
| `launch [--kill]` | Start Chrome with GFW bypass + CDP |
| `navigate` | Open/reload Gemini tab (skips if already loaded) |
| `pro-extended` | Switch to Pro Extended (auto-discovers menu indices) |
| `status` | Show tab title + model mode |
| `send "text"` | Type prompt and click send |
| `read [--full]` | Read latest response (or full text with `--full`) |
| `screenshot [path]` | Capture screenshot |
| `list` | List all Chrome tabs |
| `close` | Close Gemini tab |

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_PROXY` | `socks5://127.0.0.1:10808` | Proxy for Chrome |
| `CDP_PORT` | `9222` | Chrome DevTools Protocol port |

## Detailed Workflow (chrome_cdp.py)

### 1. Launch Chrome with GFW bypass (if not already running)

```bash
python /c/Users/Administrator/launch_gemini_chrome.py
```

This kills existing Chrome, restarts with:
- `--remote-debugging-port=9222` + `--user-data-dir`
- All GFW bypass flags (`--disable-features=OptimizationHints,Translate,HttpsUpgrades`, etc.)
- `--proxy-server=socks5://127.0.0.1:10808`
- Navigates to `https://gemini.google.com/u/0/app`

Check readiness:
```bash
python /c/Users/Administrator/chrome_cdp.py list
# Expected: "Google Gemini - https://gemini.google.com/..."
```

### 2. Verify current model mode

```bash
python /c/Users/Administrator/chrome_cdp.py eval "document.querySelector('button[aria-label*=\"模式\"]')?.ariaLabel"
# Returns e.g. '打开模式选择器，当前模式为"Flash"' or '"Pro 扩展"'
```

If already `"Pro 扩展"` — skip step 3.

### 3. Switch to Pro Extended Thinking

Current Gemini UI (v3.x, verified 2026-06-28) uses these exact selectors:

```bash
# Step 3a: Open model selector
python /c/Users/Administrator/chrome_cdp.py click "button[aria-label*=\"模式选择器\"]"
sleep 1.5

# Step 3b: Select "3.1 Pro 高等数学与代码" (index 2 in gem-menu-item list)
python /c/Users/Administrator/chrome_cdp.py click "gem-menu-item" 2
sleep 1

# Step 3c: Open model selector again (Pro was selected, menu collapsed)
python /c/Users/Administrator/chrome_cdp.py click "button[aria-label*=\"模式选择器\"]"
sleep 1.5

# Step 3d: Click "思考等级 标准" (index 3) to expand thinking submenu
python /c/Users/Administrator/chrome_cdp.py click "gem-menu-item" 3
sleep 1.5

# Step 3e: Select "扩展 擅长解决复杂问题" (index 5) for Extended Thinking
python /c/Users/Administrator/chrome_cdp.py click "gem-menu-item" 5
sleep 1

# Step 3f: Close menu
python /c/Users/Administrator/chrome_cdp.py eval "document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape'}))"

# Step 3g: Verify
python /c/Users/Administrator/chrome_cdp.py eval "document.querySelector('button[aria-label*=\"模式\"]')?.ariaLabel"
# Expected: '打开模式选择器，当前模式为"Pro 扩展"'
```

### 4. Send a prompt

```bash
# Type into Gemini's rich-text input (Quill editor, div[role="textbox"])
python /c/Users/Administrator/chrome_cdp.py type "[role=\"textbox\"]" "your prompt text here"

# Click send button
python /c/Users/Administrator/chrome_cdp.py click "button[aria-label=\"发送\"]"
```

### 5. Wait for response and read it

```bash
# Wait 8-15s for Gemini to respond (longer in Extended mode)
sleep 12

# Read latest response from the conversation container
python /c/Users/Administrator/chrome_cdp.py eval "document.querySelector('.conversation-container')?.innerText?.trim()"
```

### 6. Read full page text (fallback)

```bash
python /c/Users/Administrator/chrome_cdp.py eval "document.body.innerText.slice(0, 4000)"
```

Search for your prompt to find the response:
```bash
python /c/Users/Administrator/chrome_cdp.py eval "var text=document.body.innerText;var idx=text.indexOf('KEYWORD');if(idx>=0)text.slice(Math.max(0,idx-200), idx+1200);else 'not found'"
```

## DOM Architecture (current Gemini v3.x)

| Element | Selector | Notes |
|---------|----------|-------|
| Input box | `div[role="textbox"].ql-editor` | Quill.js rich-text, Angular zone.js |
| Send button | `button[aria-label="发送"]` | Disabled when input empty |
| Mode selector | `button[aria-label*="模式选择器"]` | Shows current mode in aria-label |
| Conversation content | `.conversation-container` | InnerText includes user + Gemini messages |
| Main app shell | `main.chat-app` | Top-level container |
| Sidebar history | `.chat-history` | List of past conversations |

## Angular Change Detection Workaround

Gemini's Quill editor is powered by Angular zone.js. `Input.insertText` (from CDP) and `page.fill()` may not trigger Angular change detection for text > 5K chars, causing the send button to remain disabled.

**Reliable patterns (tested):**

1. **Short text (< 5K chars)**: `chrome_cdp.py type` works directly.

2. **Long text (> 5K chars)**: Use clipboard trick:
   ```python
   # Trigger Angular zone.js with a keystroke first
   page.keyboard.type(',')
   # Paste via clipboard
   page.evaluate('navigator.clipboard.writeText("long text...")')
   page.keyboard.press('Control+v')
   page.keyboard.press('Backspace')  # Delete the comma
   ```

3. **Before sending**: Verify send button is enabled:
   ```js
   document.querySelector('button[aria-label="发送"]')?.disabled
   ```

## Session Management (Critical)

**DO NOT open a new tab for each interaction.** This loses context and triggers Google security checks.

- **Reuse existing tab**: Always use `chrome_cdp.py list` to find the existing Gemini tab first
- **Refresh if stuck**: `page.reload()` instead of creating a new tab
- **New conversation only when**: starting a completely new topic, or current conversation exceeds ~25 turns

## Session-specific detail

See `references/test-session-2026-06-28.md` for the exact tested commands, DOM selectors, and troubleshooting records from the initial verification session.

## Companion scripts

- `scripts/gemini_agent.py` — unified tool (launch, navigate, pro-extended, send, read, screenshot). Copy to `C:\\Users\\Administrator\\` for PATH access.

See the `local-chrome-control` skill's `templates/chrome_cdp.py` for the generic CDP controller used as fallback.

## Critical Implementation Notes (gemini_agent.py internals)

These were discovered through debugging and must be preserved if modifying the script.

### 1. CDP WebSocket MUST be shared (singleton pattern)

CDP page targets only respond to the **first WebSocket connection** opened against them. Each subsequent connection receives one empty handshake event and then hangs forever. Therefore `gemini_agent.py` uses a global `CDPClient` singleton that holds a single `websockets` connection and reuses it for every `call()` / `eval()` / `click()`.

```python
# WRONG — opens a new connection per command, will timeout:
async def cdp_call(ws_url, method, params):
    async with websockets.connect(ws_url) as ws:
        ...  # hangs after first message

# RIGHT — share one connection across all calls:
class CDPClient:
    async def call(self, method, params):
        async with self._lock:
            await self._ws.send(...)
            ...
```

### 2. `asyncio.timeout()` — NEVER `asyncio.wait_for(ws.recv())`

In `websockets` 15+, `asyncio.wait_for(ws.recv(), timeout=N)` cancels the internal recv coroutine when the timeout fires, which corrupts the WebSocket connection state. Subsequent reads on the same connection hang or throw.

```python
# WRONG — corrupts connection on timeout:
resp = await asyncio.wait_for(ws.recv(), timeout=30)

# RIGHT — wraps the entire recv loop:
try:
    async with asyncio.timeout(30):
        while True:
            resp = await ws.recv()
            if matches: return resp
except asyncio.TimeoutError:
    return {"error": "timeout"}
```

### 3. Event loop isolation

`asyncio` objects (WebSocket connections, locks) cannot be shared across `asyncio.run()` calls — each call creates a new event loop. `gemini_agent.py` handles this by opening the WebSocket connection **inside** each action's async context (within its `asyncio.run()`), using `connect_if_needed()` which only creates the connection if one doesn't already exist in the current loop context.

### 4. Message ID under the same connection

When multiplexing multiple `call()` invocations through the same WebSocket, each command must use a **unique incrementing ID**. The `CDPClient` uses a monotonic counter (`_msg_counter`) protected by `asyncio.Lock` to prevent ID collisions.

## Pitfalls

- **Menu index positions change** — if `gem-menu-item` index 2/3/5 doesn't match, re-evaluate with `document.querySelectorAll('gem-menu-item')` to discover current positions.
- **Gemini UI updates** — Google regularly changes Gemini's DOM structure. If selectors fail, use `document.body.innerText` search or `browser_snapshot` to discover current UI structure.
- **Model selector text varies by locale** — This skill assumes the Chinese (Traditional) UI with "扩展" for Extended. English UI uses "Thinking" → "Extended". Adjust aria-labels accordingly.
- **First-time login** — If no Google account is logged in, Gemini shows a login page. The user must log in once via visible Chrome window. Credentials persist in `~/.chrome-cdp-profile`.
- **Response may be streaming** — The `.conversation-container` selector may only capture partial text if read during streaming. Wait until streaming finishes (check for a visible "Stop" button disappearing).
- **Proxy must be HTTP/SOCKS5, not VLESS Reality** — VLESS Reality TLS spoofing conflicts with Chrome's BoringSSL, causing SSL handshake failures.
- **Kill Chrome before restart** — Multiple Chrome instances with conflicting CDP ports cause undefined behavior. Always kill existing Chrome first:
  ```bash
  powershell.exe -Command "Get-Process chrome -ErrorAction SilentlyContinue | Stop-Process -Force"
  ```
- **Shared WebSocket connection required** — `gemini_agent.py` uses a singleton `CDPClient`. If you modify the script, do NOT open new WebSocket connections per CDP call (they hang). Always reuse the same connection for all calls against the same page target. See "Critical Implementation Notes" above.
- **`read` may show old conversation** — The default `read` searches `document.body.innerText` for the last `"Gemini 说"` segment. For full page text use `read --full`. When sharing a session across multiple `send` commands, the conversation accumulates in the page body; `read` shows the most recent response.
