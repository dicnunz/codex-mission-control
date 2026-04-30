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
UPDATED_AT="$(date +"%Y-%m-%d %H:%M:%S %Z")"

STATUS_OUTPUT="$STATUS_OUTPUT" CMC_STATUS="$CMC_STATUS" CMC_DOCTOR="$CMC_DOCTOR" CMC_LANES="$CMC_LANES" CMC_PROJECTS="$CMC_PROJECTS" CMC_PACKET="$CMC_PACKET" UPDATED_AT="$UPDATED_AT" OUT="$OUT" python3 - <<'PY'
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


def find(pattern: str, text: str, fallback: str = "unknown") -> str:
    match = re.search(pattern, text)
    return match.group(1) if match else fallback


def esc(value: str) -> str:
    return html.escape(value, quote=True)


hub = find(r"hub: ([^\n]+)", cmc_status)
mission_count = find(r"missions: ([0-9]+)", cmc_status, "0")
locks = find(r"locks: ([^\n]+)", cmc_status)
stale = find(r"stale outboxes: ([0-9]+)", cmc_status, "0")
relay = find(r"relay: ([^\n]+)", cmc_status)
hub_ok = "hub files: ok" in cmc_status
doctor_ok = "ops files: ok" in cmc_doctor and "broken mission links: 0" in cmc_doctor

lane_items = []
held_lanes = []
for raw in cmc_lanes.splitlines():
    if not raw.startswith("- "):
        continue
    lane, _, state = raw[2:].partition(": ")
    clear = state == "clear"
    if not clear:
        held_lanes.append((lane, state))
    lane_items.append(
        f"""
        <div class="lane {'clear' if clear else 'held'}">
          <span>{esc(lane)}</span>
          <strong>{esc(state)}</strong>
        </div>
        """
    )

project_rows = []
for raw in cmc_projects.splitlines():
    if not raw.startswith("- "):
        continue
    label, _, path = raw[2:].partition(" -> ")
    project_rows.append(
        f"""
        <tr>
          <td>{esc(label)}</td>
          <td>{esc(path)}</td>
        </tr>
        """
    )

project_table = "\n".join(project_rows[:14])
if not project_table:
    project_table = '<tr><td colspan="2">No missions yet. Run cmc discover.</td></tr>'

next_command = 'cmc claim BROWSER TEST "using browser"'
if held_lanes:
    lane, _state = held_lanes[0]
    next_command = f'cmc release {lane} OWNER'

command_list = [
    ("Status", "cmc status"),
    ("Lanes", "cmc lanes"),
    ("Projects", "cmc projects"),
    ("Dashboard", "cmc dashboard"),
    ("Claim browser", 'cmc claim BROWSER TEST "using browser"'),
    ("Release browser", "cmc release BROWSER TEST"),
    (
        "Approval packet",
        'cmc packet --mission TEST --action "post update" --target "x.com" --object "exact post text" --proof "proof.png" --risk "public social" --why "testing approval flow" --stop "after one post"',
    ),
]

command_buttons = "\n".join(
    f'<button data-copy="{esc(command)}"><span>{esc(label)}</span><code>{esc(command)}</code></button>'
    for label, command in command_list
)

health_bits = [
    ("Hub files", "ok" if hub_ok else "check"),
    ("Doctor", "ok" if doctor_ok else "check"),
    ("Locks", locks),
    ("Relay", relay),
]
health_html = "\n".join(
    f'<div class="stat"><span>{esc(label)}</span><strong>{esc(value)}</strong></div>'
    for label, value in health_bits
)

doc = f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Codex Mission Control</title>
<style>
  :root {{
    color-scheme: dark;
    --bg: #090909;
    --panel: #121212;
    --panel-2: #171717;
    --line: #303030;
    --text: #f2f2f2;
    --muted: #a1a1aa;
    --good: #5eead4;
    --warn: #facc15;
    --bad: #fb7185;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", Inter, Arial, sans-serif;
  }}
  main {{
    width: min(1180px, calc(100vw - 32px));
    margin: 0 auto;
    padding: 22px 0 40px;
  }}
  header {{
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 18px;
    align-items: start;
    padding-bottom: 18px;
    border-bottom: 1px solid var(--line);
  }}
  h1 {{
    margin: 0 0 8px;
    font-size: 30px;
    line-height: 1.1;
    letter-spacing: 0;
  }}
  h2 {{
    margin: 0 0 12px;
    font-size: 15px;
    color: var(--muted);
    font-weight: 700;
    text-transform: uppercase;
  }}
  p {{
    margin: 0;
    color: var(--muted);
    overflow-wrap: anywhere;
  }}
  code, pre {{
    font-family: Menlo, Monaco, Consolas, monospace;
  }}
  .stamp {{
    color: var(--muted);
    font: 12px Menlo, monospace;
    border: 1px solid var(--line);
    border-radius: 7px;
    padding: 9px 10px;
    white-space: nowrap;
  }}
  .stats {{
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 10px;
    margin: 16px 0;
  }}
  .stat, .panel, .lane {{
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 8px;
  }}
  .stat {{
    padding: 12px;
    min-height: 72px;
  }}
  .stat span, .lane span {{
    display: block;
    color: var(--muted);
    font-size: 12px;
    margin-bottom: 8px;
  }}
  .stat strong, .lane strong {{
    font-size: 16px;
    overflow-wrap: anywhere;
  }}
  .layout {{
    display: grid;
    grid-template-columns: minmax(0, 1fr) 360px;
    gap: 14px;
  }}
  .panel {{
    padding: 14px;
    margin-bottom: 14px;
  }}
  .next {{
    background: #e7e5e4;
    color: #111;
    border: 0;
  }}
  .next h2, .next p {{ color: #3f3f46; }}
  .next code {{
    display: block;
    margin-top: 10px;
    color: #111;
    white-space: pre-wrap;
  }}
  .lanes {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 8px;
  }}
  .lane {{
    padding: 11px;
  }}
  .lane.clear strong {{ color: var(--good); }}
  .lane.held strong {{ color: var(--warn); }}
  button {{
    width: 100%;
    display: block;
    text-align: left;
    cursor: pointer;
    border: 1px solid var(--line);
    border-radius: 8px;
    background: var(--panel-2);
    color: var(--text);
    padding: 10px;
    margin-bottom: 8px;
  }}
  button:hover {{ border-color: #52525b; }}
  button span {{
    display: block;
    color: var(--muted);
    font-size: 12px;
    margin-bottom: 5px;
  }}
  button code {{
    color: var(--text);
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }}
  td {{
    border-top: 1px solid var(--line);
    padding: 9px 6px;
    vertical-align: top;
  }}
  td:first-child {{
    width: 110px;
    color: var(--text);
    font-weight: 700;
  }}
  td:last-child {{
    color: var(--muted);
    overflow-wrap: anywhere;
  }}
  pre {{
    margin: 0;
    max-height: 260px;
    overflow: auto;
    white-space: pre-wrap;
    color: #d4d4d8;
    font-size: 12px;
    line-height: 1.45;
  }}
  .footer {{
    margin-top: 12px;
    color: var(--muted);
    font-size: 12px;
  }}
  @media (max-width: 900px) {{
    header, .layout {{ display: block; }}
    .stats {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    .stamp {{ display: inline-block; margin-top: 12px; }}
  }}
</style>
<main>
  <header>
    <div>
      <h1>Mission Control</h1>
      <p>{esc(hub)}</p>
    </div>
    <div class="stamp">{esc(updated_at)}</div>
  </header>

  <section class="stats">{health_html}</section>

  <section class="layout">
    <div>
      <section class="panel next">
        <h2>Next thing to try</h2>
        <p>Run this in the terminal. It should change the lane state immediately.</p>
        <code>{esc(next_command)}</code>
      </section>

      <section class="panel">
        <h2>Surface lanes</h2>
        <div class="lanes">{''.join(lane_items)}</div>
      </section>

      <section class="panel">
        <h2>Missions</h2>
        <table>{project_table}</table>
      </section>
    </div>

    <aside>
      <section class="panel">
        <h2>Copy commands</h2>
        {command_buttons}
      </section>
      <section class="panel">
        <h2>Doctor</h2>
        <pre>{esc(cmc_doctor)}</pre>
      </section>
      <section class="panel">
        <h2>Relay</h2>
        <pre>{esc(relay_status)}</pre>
      </section>
    </aside>
  </section>

  <div class="footer">Local file. Refresh with <code>cmc dashboard</code> or <code>./scripts/status_ui.sh</code>. Missions: {esc(mission_count)}. Stale outboxes: {esc(stale)}.</div>
</main>
<script>
  document.querySelectorAll("button[data-copy]").forEach((button) => {{
    button.addEventListener("click", async () => {{
      const original = button.innerHTML;
      try {{
        await navigator.clipboard.writeText(button.dataset.copy);
        button.innerHTML = "<span>Copied</span><code>" + button.dataset.copy.replaceAll("&", "&amp;").replaceAll("<", "&lt;") + "</code>";
      }} catch (_error) {{
        button.innerHTML = "<span>Copy failed</span><code>select the command manually</code>";
      }}
      setTimeout(() => {{ button.innerHTML = original; }}, 1000);
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
