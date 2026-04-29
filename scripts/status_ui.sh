#!/bin/zsh
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
RUNTIME="$HOME/Library/Application Support/CodexRelay"
STATE_DIR="$RUNTIME/state"
OUT="$STATE_DIR/mission-control.html"
OPEN_PAGE="${1:-}"

mkdir -p "$STATE_DIR"
chmod 700 "$RUNTIME" "$STATE_DIR" 2>/dev/null || true

STATUS_OUTPUT="$("$ROOT/scripts/status.sh" 2>&1 || true)"
CMC_STATUS="$("$ROOT/cmc" status 2>&1 || true)"
CMC_DOCTOR="$("$ROOT/cmc" doctor 2>&1 || true)"
CMC_LANES="$("$ROOT/cmc" lanes 2>&1 || true)"
CMC_PROJECTS="$("$ROOT/cmc" projects 2>&1 || true)"
CMC_PACKET="$("$ROOT/cmc" packet 2>&1 || true)"
UPDATED_AT="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

STATUS_OUTPUT="$STATUS_OUTPUT" CMC_STATUS="$CMC_STATUS" CMC_DOCTOR="$CMC_DOCTOR" CMC_LANES="$CMC_LANES" CMC_PROJECTS="$CMC_PROJECTS" CMC_PACKET="$CMC_PACKET" UPDATED_AT="$UPDATED_AT" OUT="$OUT" ROOT="$ROOT" python3 - <<'PY'
import html
import os
import re
from pathlib import Path

relay_status = os.environ["STATUS_OUTPUT"]
cmc_status = os.environ["CMC_STATUS"]
cmc_doctor = os.environ["CMC_DOCTOR"]
cmc_lanes = os.environ["CMC_LANES"]
cmc_projects = os.environ["CMC_PROJECTS"]
cmc_packet = os.environ["CMC_PACKET"]
updated_at = os.environ["UPDATED_AT"]
out = Path(os.environ["OUT"])
root = Path(os.environ["ROOT"])
visual_path = root / "assets/visuals/dashboard-instrument.png"
icon_path = root / "assets/visuals/mission-control-icon.png"

def find(pattern: str, text: str, fallback: str = "0") -> str:
    match = re.search(pattern, text)
    return match.group(1) if match else fallback

mission_count = find(r"missions: ([0-9]+)", cmc_status)
lock_line = find(r"locks: ([^\n]+)", cmc_status, "unknown")
outboxes = find(r"stale outboxes: ([0-9]+)", cmc_status)
relay = find(r"relay: ([^\n]+)", cmc_status, "unknown")
hub = find(r"hub: ([^\n]+)", cmc_status, "unknown")

lane_rows = []
for line in cmc_lanes.splitlines():
    if not line.startswith("- "):
        continue
    name, _, state = line[2:].partition(": ")
    ok = state == "clear"
    lane_rows.append(
        f"<div class='lane {'clear' if ok else 'held'}'><span>{html.escape(name)}</span><b>{html.escape(state)}</b></div>"
    )

project_rows = []
for line in cmc_projects.splitlines():
    if not line.startswith("- "):
        continue
    label, _, path = line[2:].partition(" -> ")
    project_rows.append(
        f"<div class='project'><b>{html.escape(label)}</b><span>{html.escape(path)}</span></div>"
    )
project_html = "\n".join(project_rows[:10]) or "<div class='empty'>Run <code>cmc discover</code> to add missions.</div>"
if len(project_rows) > 10:
    project_html += f"\n<div class='empty'>{len(project_rows) - 10} more missions in <code>cmc projects</code>.</div>"

cards = "\n".join(
    [
        f"<div class='metric'><span>Missions</span><b>{html.escape(mission_count)}</b></div>",
        f"<div class='metric'><span>Lanes</span><b>{html.escape(lock_line)}</b></div>",
        f"<div class='metric'><span>Stale outboxes</span><b>{html.escape(outboxes)}</b></div>",
        f"<div class='metric'><span>Relay</span><b>{html.escape(relay)}</b></div>",
    ]
)

commands = "\n".join(
    [
        "cmc status",
        "cmc lanes",
        "cmc projects",
        "cmc packet",
        "cmc claim BROWSER FLIGHT \"reason\"",
        "cmc release BROWSER FLIGHT",
        "/mission status",
        "/mission lanes",
        "/mission packet",
        "/mission health",
    ]
)

visual_html = ""
if visual_path.exists():
    visual_html = (
        f"<section class='visual-hero'><img src='{html.escape(visual_path.as_uri(), quote=True)}' "
        "alt='Codex Mission Control dashboard visual'></section>"
    )

doc = f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Codex Mission Control</title>
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
    width: min(1160px, calc(100vw - 40px));
    margin: 0 auto;
    padding: 44px 0;
  }}
  header {{
    display: flex;
    justify-content: space-between;
    gap: 24px;
    align-items: flex-start;
    border-bottom: 1px solid #27272a;
    padding-bottom: 28px;
  }}
  .visual-hero {{
    margin: 28px 0 0;
    border: 1px solid #27272a;
    border-radius: 8px;
    overflow: hidden;
    background: #0b0b0b;
  }}
  .visual-hero img {{
    display: block;
    width: 100%;
    height: auto;
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
    font-size: clamp(34px, 6vw, 68px);
    line-height: .96;
    letter-spacing: 0;
  }}
  p {{ color: #b8b8b8; margin: 0; font-size: 17px; max-width: 720px; }}
  code {{ color: #e5e5e5; }}
  .pill {{
    border: 1px solid #2f2f35;
    border-radius: 999px;
    padding: 9px 14px;
    color: #a7f3d0;
    font-family: Menlo, monospace;
    white-space: nowrap;
  }}
  .brand {{
    display: flex;
    gap: 14px;
    align-items: center;
  }}
  .brand img {{
    width: 46px;
    height: 46px;
    border-radius: 10px;
  }}
  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
    gap: 12px;
    margin: 28px 0;
  }}
  .metric, .panel, .lane, .project {{
    border: 1px solid #2f2f35;
    border-radius: 8px;
    background: #101010;
  }}
  .metric {{
    padding: 14px;
    min-height: 88px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
  }}
  .metric span, .project span, .lane span {{ color: #b8b8b8; }}
  .metric b {{ color: #f5f5f5; font-size: 22px; overflow-wrap: anywhere; }}
  .row {{
    display: grid;
    grid-template-columns: minmax(0, 1.2fr) minmax(320px, .8fr);
    gap: 16px;
    margin: 16px 0;
  }}
  .panel {{ padding: 18px; }}
  .panel h2 {{ font-size: 18px; margin: 0 0 14px; }}
  .lanes {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
    gap: 10px;
  }}
  .lane {{ padding: 12px; min-height: 74px; }}
  .lane b {{ display: block; margin-top: 10px; font-size: 15px; overflow-wrap: anywhere; }}
  .lane.clear b {{ color: #5eead4; }}
  .lane.held b {{ color: #fbbf24; }}
  .projects {{ display: grid; gap: 8px; }}
  .project {{ padding: 12px; }}
  .project b {{ display: block; color: #f5f5f5; margin-bottom: 6px; }}
  .project span {{ font-size: 13px; overflow-wrap: anywhere; }}
  .actions {{ display: grid; gap: 10px; }}
  button {{
    appearance: none;
    border: 1px solid #3f3f46;
    background: #f5f5f5;
    color: #111111;
    border-radius: 8px;
    padding: 11px 12px;
    font-weight: 700;
    text-align: left;
    cursor: pointer;
  }}
  button.secondary {{ background: #111111; color: #f5f5f5; }}
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
  .empty {{ color: #8b8b8b; padding: 10px 0; }}
  footer {{ color: #737373; margin-top: 16px; font-size: 13px; }}
  @media (max-width: 820px) {{
    header, .row {{ display: block; }}
    .pill {{ display: inline-block; margin-top: 18px; }}
    .panel {{ margin-bottom: 16px; }}
  }}
</style>
<main>
  <header>
    <div>
      <div class="brand">
        {f"<img src='{html.escape(icon_path.as_uri(), quote=True)}' alt=''>" if icon_path.exists() else ""}
        <div class="eyebrow">Codex Mission Control</div>
      </div>
      <h1>Your Codex control room.</h1>
      <p>{html.escape(hub)}</p>
    </div>
    <div class="pill">{html.escape(updated_at)}</div>
  </header>
  {visual_html}
  <section class="grid">{cards}</section>
  <section class="row">
    <div class="panel">
      <h2>Surface lanes</h2>
      <div class="lanes">{''.join(lane_rows)}</div>
    </div>
    <div class="panel">
      <h2>One-tap commands</h2>
      <div class="actions">
        <button data-copy="cmc status">Copy <code>cmc status</code></button>
        <button data-copy="cmc claim BROWSER FLIGHT &quot;reason&quot;">Copy browser claim</button>
        <button data-copy="{html.escape(cmc_packet, quote=True)}">Copy approval packet</button>
        <button class="secondary" data-copy="{html.escape(commands, quote=True)}">Copy command list</button>
      </div>
    </div>
  </section>
  <section class="row">
    <div class="panel">
      <h2>Missions</h2>
      <div class="projects">{project_html}</div>
    </div>
    <div class="panel">
      <h2>Doctor</h2>
      <pre>{html.escape(cmc_doctor)}</pre>
    </div>
  </section>
  <section class="panel">
    <h2>Relay runtime</h2>
    <pre>{html.escape(relay_status)}</pre>
  </section>
  <footer>Refresh with <code>./scripts/status_ui.sh</code>. This file is local and private.</footer>
</main>
<script>
  document.querySelectorAll('button[data-copy]').forEach((button) => {{
    button.addEventListener('click', async () => {{
      const original = button.textContent;
      try {{
        await navigator.clipboard.writeText(button.dataset.copy);
        button.textContent = 'Copied';
        setTimeout(() => button.textContent = original, 1200);
      }} catch (_error) {{
        button.textContent = 'Copy failed';
        setTimeout(() => button.textContent = original, 1200);
      }}
    }});
  }});
</script>
</html>
"""

out.write_text(doc)
out.chmod(0o600)
print(out)
PY

if [[ "$OPEN_PAGE" != "--no-open" ]]; then
  open "$OUT"
fi
