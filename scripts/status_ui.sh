#!/bin/zsh
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
RUNTIME="$HOME/Library/Application Support/CodexRelay"
STATE_DIR="$RUNTIME/state"
OUT="$STATE_DIR/status.html"

mkdir -p "$STATE_DIR"
chmod 700 "$RUNTIME" "$STATE_DIR" 2>/dev/null || true

STATUS_OUTPUT="$("$ROOT/scripts/status.sh" 2>&1 || true)"
UPDATED_AT="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

STATUS_OUTPUT="$STATUS_OUTPUT" UPDATED_AT="$UPDATED_AT" OUT="$OUT" python3 - <<'PY'
import html
import os
from pathlib import Path

status = os.environ["STATUS_OUTPUT"]
updated_at = os.environ["UPDATED_AT"]
out = Path(os.environ["OUT"])

checks = []
for label, needle in [
    ("LaunchAgent", "state = running"),
    ("Token", "TELEGRAM_BOT_TOKEN=set"),
    ("Model", "model="),
    ("Thinking", "thinking_mode="),
    ("Speed", "speed="),
    ("Style", "reply_style="),
    ("Images", "telegram_images=enabled"),
]:
    checks.append((label, needle in status))

rows = "\n".join(
    f"<div class='check {'ok' if ok else 'warn'}'><span>{html.escape(label)}</span><b>{'ok' if ok else 'check'}</b></div>"
    for label, ok in checks
)

doc = f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Codex Relay Status</title>
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    min-height: 100vh;
    background: #050505;
    color: #f5f5f5;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", Inter, Arial, sans-serif;
  }}
  main {{
    width: min(980px, calc(100vw - 40px));
    margin: 0 auto;
    padding: 52px 0;
  }}
  header {{
    display: flex;
    justify-content: space-between;
    gap: 24px;
    align-items: flex-start;
    border-bottom: 1px solid #27272a;
    padding-bottom: 28px;
  }}
  .eyebrow {{
    color: #8b8b8b;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: .08em;
    text-transform: uppercase;
  }}
  h1 {{
    margin: 8px 0 10px;
    font-size: clamp(36px, 6vw, 72px);
    line-height: .96;
    letter-spacing: 0;
  }}
  p {{ color: #b8b8b8; margin: 0; font-size: 18px; }}
  .pill {{
    border: 1px solid #2f2f35;
    border-radius: 999px;
    padding: 9px 14px;
    color: #a7f3d0;
    font-family: Menlo, monospace;
    white-space: nowrap;
  }}
  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(145px, 1fr));
    gap: 12px;
    margin: 28px 0;
  }}
  .check {{
    border: 1px solid #2f2f35;
    border-radius: 8px;
    background: #101010;
    padding: 14px;
    min-height: 88px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
  }}
  .check span {{ color: #b8b8b8; }}
  .check b {{ color: #f5f5f5; font-size: 22px; }}
  .check.ok b {{ color: #5eead4; }}
  .check.warn b {{ color: #fbbf24; }}
  pre {{
    margin: 0;
    border: 1px solid #2f2f35;
    border-radius: 8px;
    background: #0b0b0b;
    padding: 18px;
    overflow: auto;
    color: #d4d4d4;
    font: 13px/1.5 Menlo, monospace;
  }}
  footer {{ color: #737373; margin-top: 16px; font-size: 13px; }}
</style>
<main>
  <header>
    <div>
      <div class="eyebrow">Codex Relay</div>
      <h1>Mac bridge status.</h1>
      <p>Private local status page generated from <code>./scripts/status.sh</code>.</p>
    </div>
    <div class="pill">{html.escape(updated_at)}</div>
  </header>
  <section class="grid">{rows}</section>
  <pre>{html.escape(status)}</pre>
  <footer>Refresh by running <code>./scripts/status_ui.sh</code>.</footer>
</main>
</html>
"""

out.write_text(doc)
out.chmod(0o600)
print(out)
PY

open "$OUT"
