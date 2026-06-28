# Gemini Web CDP Test Session (2026-06-28)

## Final Verified Pipeline

### Environment
- OS: Windows 10
- Proxy: v2rayN SOCKS5 `127.0.0.1:10808`
- Chrome 149 (CDP port 9222, profile `~/.chrome-cdp-profile`)
- Controller: `gemini_agent.py` (single shared WebSocket connection)

### Verified Commands

```bash
python gemini_agent.py status           # Tab + Mode info
python gemini_agent.py send "prompt"    # Send message
python gemini_agent.py read             # Read last Gemini response
python gemini_agent.py read --full      # Read full page text
python gemini_agent.py screenshot path  # Save screenshot
python gemini_agent.py list             # List all tabs
python gemini_agent.py pro-extended     # Switch to Pro Extended
python gemini_agent.py close            # Close Gemini tab
```

### DOM Selectors (Gemini v3.x, Traditional Chinese)

| Element | Selector | Verified |
|---------|----------|----------|
| Input | `div[role="textbox"].ql-editor` | ✅ |
| Send button | `button[aria-label="发送"]` | ✅ May need Angular trigger |
| Mode selector | `button[aria-label*="模式选择器"]` | ✅ |
| Menu items | `gem-menu-item` | ✅ Dynamic indices |

### Menu Layout (Pro Extended)

```
index 0: "3.1 Flash-Lite / 极速回答"
index 1: "3.5 Flash / 全方位帮助"
index 2: "3.1 Pro / 高等数学与代码"   ← click for Pro
index 3: "思考等级 / 标准"           ← click to expand
  index 4: "标准 / 最适合回答大多数问题"
  index 5: "扩展 / 擅长解决复杂问题"   ← Extended Thinking
```

### Critical Discoveries

1. **CDP WebSocket must be SHARED** — Each CDP page target only responds on the first WebSocket connection. Opening new connections per call causes timeouts. Use a singleton `CDPClient` with one persistent WebSocket.

2. **`asyncio.timeout()` not `wait_for()`** — In websockets 15, `asyncio.wait_for(ws.recv(), timeout=N)` cancels the recv coroutine on timeout, corrupting the connection. Use `async with asyncio.timeout(N):` wrapping the entire recv loop instead.

3. **Event loop isolation** — asyncio objects (WebSocket connections) cannot be shared across `asyncio.run()` calls. All async operations must run within a single event loop per action.

4. **GFW bypass flags** are essential in China (confirmed working):
   - `--disable-features=OptimizationHints,Translate,HttpsUpgrades`
   - `--disable-background-networking`
   - `--disable-client-side-phishing-detection`
   - `--disable-field-trial-config`
   - `--disable-component-update`
   - `--proxy-server=socks5://127.0.0.1:10808` (not VLESS Reality)
