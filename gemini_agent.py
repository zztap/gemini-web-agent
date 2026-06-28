#!/usr/bin/env python3
"""
Gemini Web Agent — Hermes skill companion script.
Drive Gemini Web (gemini.google.com) via Chrome CDP.

Usage:
  python gemini_agent.py launch              # Start Chrome with GFW bypass + CDP
  python gemini_agent.py launch --kill       # Force restart Chrome
  python gemini_agent.py navigate            # Open/reload Gemini
  python gemini_agent.py pro-extended        # Switch to Pro Extended Thinking
  python gemini_agent.py status              # Show current mode
  python gemini_agent.py send "your prompt"  # Send message to Gemini
  python gemini_agent.py read                # Read latest response
  python gemini_agent.py read --full         # Read full conversation
  python gemini_agent.py screenshot <path>   # Capture screenshot
  python gemini_agent.py list                # List all tabs
  python gemini_agent.py close               # Close Gemini tab
"""
import os, sys, time, json, socket, subprocess, base64, re, asyncio
import urllib.request

# Auto-install missing deps
for _pkg in ["websockets", "requests"]:
    try:
        __import__(_pkg.replace("-", "_"))
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", _pkg], capture_output=True)

import websockets
import requests

CDP_PORT = int(os.environ.get("CDP_PORT", "9222"))
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PROFILE_DIR = os.path.expanduser(r"~\.chrome-cdp-profile")
PROXY = os.environ.get("GEMINI_PROXY", "socks5://127.0.0.1:10808")
GEMINI_URL = "https://gemini.google.com/u/0/app"

# ---- Shared CDP WebSocket connection ----
# CRITICAL: CDP page targets only respond on the FIRST WebSocket connection.
# Each new connection gets one empty event then hangs. Always reuse one WS.

class CDPClient:
    """Singleton CDP WebSocket client — one connection, reused for all calls."""
    def __init__(self):
        self._ws = None
        self._ws_url = None
        self._msg_counter = 0
        self._lock = asyncio.Lock()

    async def connect(self, ws_url):
        """Open/reconnect WebSocket."""
        await self.close()
        self._ws = await websockets.connect(ws_url, max_size=10_485_760)
        self._ws_url = ws_url
        # Drain initial handshake events
        for _ in range(5):
            try:
                async with asyncio.timeout(0.5):
                    await self._ws.recv()
            except (asyncio.TimeoutError, websockets.ConnectionClosed):
                break

    async def call(self, method, params=None, timeout=30):
        """Send CDP command and wait for response on the shared connection."""
        async with self._lock:
            self._msg_counter += 1
            msg_id = self._msg_counter
            cmd = {"id": msg_id, "method": method, "params": params or {}}
            await self._ws.send(json.dumps(cmd))
            try:
                async with asyncio.timeout(timeout):
                    while True:
                        resp = await self._ws.recv()
                        data = json.loads(resp)
                        if data.get("id") == msg_id:
                            return data
            except asyncio.TimeoutError:
                return {"error": "timeout"}

    async def eval(self, js, timeout=30):
        """Evaluate JavaScript and return the result value."""
        result = await self.call("Runtime.evaluate",
                                 {"expression": js, "returnByValue": True}, timeout=timeout)
        if result and "result" in result and "result" in result["result"]:
            return result["result"]["result"].get("value")
        return None

    async def click(self, selector, index=0):
        """Click element by CSS selector via real mouse events."""
        js = f"""
        (() => {{
            const els = document.querySelectorAll({json.dumps(selector)});
            if (!els.length) return {{error: 'not found: ' + {json.dumps(selector)}}};
            const el = els[{index}];
            const rect = el.getBoundingClientRect();
            return {{x: rect.left + rect.width/2, y: rect.top + rect.height/2,
                    tag: el.tagName, text: (el.textContent||'').trim().slice(0,50)}};
        }})()
        """
        val = await self.eval(js)
        if not val or "error" in val:
            print(f"  ❌ {val.get('error', 'click failed')}")
            return False
        x, y = val["x"], val["y"]
        await self.call("Input.dispatchMouseEvent",
                        {"type": "mouseMoved", "x": x, "y": y})
        await self.call("Input.dispatchMouseEvent",
                        {"type": "mousePressed", "button": "left", "x": x, "y": y, "clickCount": 1})
        await self.call("Input.dispatchMouseEvent",
                        {"type": "mouseReleased", "button": "left", "x": x, "y": y, "clickCount": 1})
        return True

    async def screenshot(self, filepath):
        """Capture screenshot."""
        result = await self.call("Page.captureScreenshot", {"format": "png"})
        if result and "result" in result and "data" in result["result"]:
            img_data = base64.b64decode(result["result"]["data"])
            with open(filepath, "wb") as f:
                f.write(img_data)
            return filepath
        return None

    async def close(self):
        if self._ws:
            await self._ws.close()
            self._ws = None
            self._ws_url = None

# Global CDP client instance
_cdp = CDPClient()

# ---- Low-level HTTP helpers ----

def cdp_url(path="/json"):
    return f"http://127.0.0.1:{CDP_PORT}{path}"

def port_open(port, timeout=2):
    s = socket.socket()
    s.settimeout(timeout)
    try:
        return s.connect_ex(("127.0.0.1", port)) == 0
    finally:
        s.close()

def http_get(path):
    return json.loads(urllib.request.urlopen(cdp_url(path), timeout=5).read())

def http_put(path, data=None):
    req = urllib.request.Request(cdp_url(path), method="PUT",
                                 data=data.encode() if data else None)
    return json.loads(urllib.request.urlopen(req, timeout=5).read())

def get_gemini_ws():
    """Get WebSocket URL for a Gemini page tab."""
    targets = http_get("/json")
    for t in targets:
        if t["type"] == "page" and "gemini" in t.get("url", "").lower():
            title = t.get("title", "")
            if title and title != "about:blank":
                return t["webSocketDebuggerUrl"]
    for t in targets:
        if t["type"] == "page":
            return t["webSocketDebuggerUrl"]
    return None

# ---- Actions ----

def action_launch(kill=False):
    """Launch Chrome with GFW bypass flags + CDP."""
    if port_open(CDP_PORT) and not kill:
        print(f"Chrome CDP already running on port {CDP_PORT}")
        return True

    if kill or port_open(CDP_PORT):
        print("Killing existing Chrome...")
        subprocess.run(
            ['powershell.exe', '-Command',
             'Get-Process chrome -ErrorAction SilentlyContinue | Stop-Process -Force'],
            shell=False, capture_output=True)
        time.sleep(3)

    os.makedirs(PROFILE_DIR, exist_ok=True)
    print(f"Launching Chrome (CDP:{CDP_PORT}, proxy:{PROXY})...")

    cmd = [
        CHROME_PATH,
        f"--remote-debugging-port={CDP_PORT}",
        f"--user-data-dir={PROFILE_DIR}",
        "--disable-features=OptimizationHints,Translate,HttpsUpgrades",
        "--disable-background-networking",
        "--disable-client-side-phishing-detection",
        "--disable-field-trial-config",
        "--disable-component-update",
        "--disable-sync",
        "--no-first-run",
        "--no-default-browser-check",
        "--restore-last-session",
        f"--proxy-server={PROXY}",
    ]

    subprocess.Popen(cmd, shell=False)

    for i in range(30):
        time.sleep(0.5)
        if port_open(CDP_PORT):
            print(f"✅ Chrome ready (CDP port {CDP_PORT})")
            return True

    print("❌ Chrome CDP port timeout")
    return False

def ensure_cdp_connected():
    """Ensure CDP client has a live connection to the Gemini tab.
    Returns ws_url or None. Call inside the action's async context."""
    ws_url = get_gemini_ws()
    if not ws_url:
        return None
    return ws_url

async def connect_if_needed(ws_url):
    """Async: connect CDP client if not already connected."""
    global _cdp
    if _cdp._ws is None or _cdp._ws_url != ws_url:
        await _cdp.connect(ws_url)
    return True

def action_navigate():
    """Navigate Chrome to Gemini."""
    if not port_open(CDP_PORT):
        print("CDP not running. Call 'launch' first.")
        return False

    # Check if Gemini tab already exists
    ws_url = get_gemini_ws()
    if ws_url:
        asyncio.run(ensure_cdp_connected())
        title = asyncio.run(_cdp.eval("document.title"))
        if title and title != "about:blank":
            print(f"✅ Gemini already open: {title}")
            return True

    # Open new tab and navigate
    try:
        tab = http_put("/json/new?url=about:blank")
        ws_url = tab.get("webSocketDebuggerUrl")
        if not ws_url:
            print("❌ Failed to create tab")
            return False

        async def _nav():
            await _cdp.connect(ws_url)
            await _cdp.call("Page.enable")
            result = await _cdp.call("Page.navigate", {"url": GEMINI_URL})
            return result

        result = asyncio.run(_nav())
        print(f"✅ Navigating to Gemini: {result.get('result', {}).get('url', 'ok')}")
        return True
    except Exception as e:
        print(f"❌ Navigation error: {e}")
        return False

def action_pro_extended():
    """Switch Gemini to Pro Extended Thinking mode."""
    async def _switch():
        ws_url = ensure_cdp_connected()
        if not ws_url:
            print("❌ No Gemini tab found. Call 'navigate' first.")
            return False
        await connect_if_needed(ws_url)
        cdp = _cdp

        # Step 1: Open model selector
        if not await cdp.click("button[aria-label*=\"模式选择器\"]"):
            print("  ❌ Model selector not found")
            return False
        await asyncio.sleep(1.5)

        # Step 2: Discover menu items
        items = await cdp.eval(
            "Array.from(document.querySelectorAll('gem-menu-item')).map((e,i)=>({i:i,t:e.innerText.trim()}))")
        print(f"Menu items: {json.dumps(items, ensure_ascii=False)}")

        # Step 3: Find and click Pro
        pro_idx = None
        for item in (items or []):
            t = item.get("t", "")
            if "Pro" in t and "Flash" not in t:
                pro_idx = item["i"]
                break
        if pro_idx is not None:
            await cdp.click("gem-menu-item", index=pro_idx)
            print(f"  Selected Pro (index {pro_idx})")
            await asyncio.sleep(1)
        else:
            print("  ⚠️ Pro option not found")

        # Step 4: Reopen model selector
        await cdp.click("button[aria-label*=\"模式选择器\"]")
        await asyncio.sleep(1.5)

        # Step 5: Find thinking level
        items = await cdp.eval(
            "Array.from(document.querySelectorAll('gem-menu-item')).map((e,i)=>({i:i,t:e.innerText.trim()}))")

        thinking_idx = None
        for item in (items or []):
            t = item.get("t", "")
            if "思考" in t or "Thinking" in t:
                thinking_idx = item["i"]
                break

        if thinking_idx is not None:
            await cdp.click("gem-menu-item", index=thinking_idx)
            print(f"  Opened thinking level (index {thinking_idx})")
            await asyncio.sleep(1.5)

            items = await cdp.eval(
                "Array.from(document.querySelectorAll('gem-menu-item')).map((e,i)=>({i:i,t:e.innerText.trim()}))")

            ext_idx = None
            for item in (items or []):
                t = item.get("t", "")
                if "扩展" in t or "Extended" in t or "延長" in t:
                    ext_idx = item["i"]
                    break
            if ext_idx is None and items and len(items) > 4:
                ext_idx = len(items) - 1

            if ext_idx is not None:
                await cdp.click("gem-menu-item", index=ext_idx)
                print(f"  Selected Extended Thinking (index {ext_idx})")
                await asyncio.sleep(1)
            else:
                print("  ⚠️ Extended option not found")
        else:
            print("  ⚠️ Thinking level option not found")

        # Close menu
        await cdp.eval(
            "document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape'}))")
        await asyncio.sleep(1)

        # Verify
        label = await cdp.eval(
            "document.querySelector('button[aria-label*=\"模式\"]')?.ariaLabel")
        print(f"  Mode: {label}")
        if label and "Pro" in str(label) and ("扩展" in str(label) or "Extended" in str(label)):
            print("✅ Pro Extended Thinking is active!")
            return True
        elif label and "Pro" in str(label):
            print("ℹ️  Pro mode active (Extended may not be enabled)")
            return True
        else:
            print("⚠️ Mode switch may not have completed")
            return False

    return asyncio.run(_switch())

def action_status():
    """Check current Gemini mode and tab title."""
    async def _check():
        ws_url = ensure_cdp_connected()
        if not ws_url:
            print("❌ No Gemini tab found")
            return
        await connect_if_needed(ws_url)
        cdp = _cdp
        label = await cdp.eval(
            "document.querySelector('button[aria-label*=\"模式\"]')?.ariaLabel || 'not found'")
        title = await cdp.eval("document.title")

        print(f"Tab:  {title or 'unknown'}")
        print(f"Mode: {label or 'unknown'}")
        if label and "Pro" in str(label) and ("扩展" in str(label) or "Extended" in str(label)):
            print("✅ Pro Extended Thinking is active")
        elif label and "Pro" in str(label):
            print("ℹ️  Pro mode (Extended not enabled)")
        elif label and "Flash" in str(label):
            print("ℹ️  Flash mode")
        else:
            print("ℹ️  Unknown mode")

    asyncio.run(_check())

def action_send(text):
    """Send a prompt to Gemini."""
    async def _send():
        ws_url = ensure_cdp_connected()
        if not ws_url:
            print("❌ No Gemini tab found. Call 'navigate' first.")
            return
        await connect_if_needed(ws_url)
        cdp = _cdp
        # Focus textbox
        focus_js = """
        (() => {
            const el = document.querySelector('div[role="textbox"].ql-editor');
            if (!el) return {error: 'textbox not found'};
            el.focus();
            el.innerText = '';
            return {ok: true};
        })()
        """
        val = await cdp.eval(focus_js)
        if isinstance(val, dict) and "error" in val:
            print(f"❌ {val['error']}")
            return

        # Type text
        await cdp.call("Input.insertText", {"text": text})
        await asyncio.sleep(0.5)

        # Click send button
        send_js = """
        (() => {
            const btn = document.querySelector('button[aria-label="发送"]');
            if (!btn) return {error: 'send button not found'};
            if (btn.disabled) return {error: 'button disabled (Angular change detection)'};
            const rect = btn.getBoundingClientRect();
            return {x: rect.left + rect.width/2, y: rect.top + rect.height/2};
        })()
        """
        val = await cdp.eval(send_js)
        if isinstance(val, dict) and "error" in val:
            if "disabled" in val.get("error", ""):
                print("  ⚠️ Send button disabled. Trying Angular trigger...")
                await cdp.call("Input.insertText", {"text": " "})
                await asyncio.sleep(0.3)
                await cdp.call("Input.deleteContentBackward", {})
                await asyncio.sleep(0.3)
                val = await cdp.eval(send_js)
            if isinstance(val, dict) and "error" in val:
                print(f"  ❌ {val['error']}")
                return

        x, y = val["x"], val["y"]
        await cdp.call("Input.dispatchMouseEvent",
                       {"type": "mouseMoved", "x": x, "y": y})
        await cdp.call("Input.dispatchMouseEvent",
                       {"type": "mousePressed", "button": "left", "x": x, "y": y, "clickCount": 1})
        await cdp.call("Input.dispatchMouseEvent",
                       {"type": "mouseReleased", "button": "left", "x": x, "y": y, "clickCount": 1})

        print(f"✅ Prompt sent ({len(text)} chars)")
        print(f"   \"{text[:80]}{'...' if len(text)>80 else ''}\"")

    asyncio.run(_send())

def action_read(full=False):
    """Read Gemini's response."""
    async def _read():
        ws_url = ensure_cdp_connected()
        if not ws_url:
            print("❌ No Gemini tab found")
            return
        await connect_if_needed(ws_url)
        if full:
            expr = "document.body.innerText"
        else:
            expr = ("(function(){var t=document.body.innerText;var i=t.lastIndexOf('Gemini 说');"
                    "return i>=0?t.slice(i, i+3000):t.slice(-4000);})()")

        text = await _cdp.eval(expr)
        if text:
            print(str(text).strip())
        else:
            print("(empty - may still be loading)")

    asyncio.run(_read())

def action_screenshot(filepath=None):
    """Take a screenshot of the current page."""
    async def _shot():
        ws_url = ensure_cdp_connected()
        if not ws_url:
            print("❌ No tab found")
            return
        await connect_if_needed(ws_url)
        fpath = filepath or os.path.expanduser("~/gemini_screenshot.png")
        path = await _cdp.screenshot(fpath)
        if path:
            print(f"📸 Screenshot saved: {path}")
            print(f"MEDIA:{path}")
        else:
            print("❌ Screenshot failed")

    asyncio.run(_shot())

def action_list():
    """List all tabs."""
    targets = http_get("/json")
    if not targets:
        print("No targets found")
        return
    for t in targets:
        if t["type"] == "page":
            tid = t.get("id", "????")[:8]
            title = t.get("title", "untitled")
            url = t.get("url", "")[:80]
            marker = " ← Gemini" if "gemini" in url.lower() else ""
            print(f"  [{tid}] {title}{marker}")

def action_close():
    """Close Gemini tab."""
    targets = http_get("/json")
    for t in targets:
        if t["type"] == "page" and "gemini" in t.get("url", "").lower():
            try:
                http_get(f"/json/close/{t['id']}")
                print(f"Closed Gemini tab: {t.get('title', 'untitled')}")
            except Exception as e:
                print(f"Error: {e}")

# ---- Main ----

def print_usage():
    print(__doc__.strip())

def main():
    if len(sys.argv) < 2:
        print_usage()
        return

    action = sys.argv[1]

    if action == "launch":
        action_launch(kill="--kill" in sys.argv)
    elif action == "navigate":
        action_navigate()
    elif action == "pro-extended":
        action_pro_extended()
    elif action == "status":
        action_status()
    elif action == "send":
        if len(sys.argv) < 3:
            print("Usage: gemini_agent.py send \"your prompt\"")
            return
        action_send(" ".join(sys.argv[2:]))
    elif action == "read":
        action_read(full="--full" in sys.argv)
    elif action == "screenshot":
        path = sys.argv[2] if len(sys.argv) > 2 else None
        action_screenshot(path)
    elif action == "list":
        action_list()
    elif action == "close":
        action_close()
    else:
        print(f"Unknown action: {action}")
        print_usage()

if __name__ == "__main__":
    main()
