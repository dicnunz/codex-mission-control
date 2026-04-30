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
UPDATED_AT="$(date +"%H:%M %Z")"

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


def find(pattern: str, text: str, fallback: str = "") -> str:
    match = re.search(pattern, text)
    return match.group(1) if match else fallback


def esc(value: str) -> str:
    return html.escape(value, quote=True)


def parse_owner(state: str) -> str:
    match = re.match(r"held by ([^ ]+)", state)
    return match.group(1) if match else "OWNER"


hub = find(r"hub: ([^\n]+)", cmc_status, "unknown hub")
mission_count = find(r"missions: ([0-9]+)", cmc_status, "0")
locks = find(r"locks: ([^\n]+)", cmc_status, "unknown")
relay = find(r"relay: ([^\n]+)", cmc_status, "unknown")
hub_ok = "hub files: ok" in cmc_status
doctor_ok = "ops files: ok" in cmc_doctor and "broken mission links: 0" in cmc_doctor
ready = hub_ok and doctor_ok

lanes = []
held = []
for raw in cmc_lanes.splitlines():
    if not raw.startswith("- "):
        continue
    lane, _, state = raw[2:].partition(": ")
    item = {"lane": lane, "state": state, "clear": state == "clear", "owner": parse_owner(state)}
    lanes.append(item)
    if not item["clear"]:
        held.append(item)

primary = held[0] if held else None
if primary:
    main_label = f"{primary['lane']} is held"
    main_detail = primary["state"]
    main_command = f"cmc release {primary['lane']} {primary['owner']}"
    main_note = "Free the surface, then hand it to the next chat."
    body_class = "blocked"
else:
    main_label = "All lanes are clear"
    main_detail = "Ready for the next Codex chat."
    main_command = 'cmc claim BROWSER TEST "using browser"'
    main_note = "Claim the surface before a chat touches the browser, GitHub, email, social, commerce, desktop, or global state."
    body_class = "ready"

lane_rows = "\n".join(
    f"""
    <tr class="{'clear' if item['clear'] else 'held'}">
      <td>{esc(item['lane'])}</td>
      <td>{esc(item['state'])}</td>
    </tr>
    """
    for item in lanes
)

projects = []
for raw in cmc_projects.splitlines():
    if not raw.startswith("- "):
        continue
    left, _, path = raw[2:].partition(" -> ")
    call_sign, _, name = left.partition(": ")
    projects.append((call_sign.strip(), name.strip() or left.strip(), path.strip()))

project_rows = "\n".join(
    f"""
    <tr>
      <td>{esc(call)}</td>
      <td>{esc(name)}</td>
      <td>{esc(path)}</td>
    </tr>
    """
    for call, name, path in projects[:8]
)
if not project_rows:
    project_rows = '<tr><td colspan="3">No missions yet.</td></tr>'
more_projects = max(0, len(projects) - 8)

quick_commands = [
    ("status", "cmc status"),
    ("lanes", "cmc lanes"),
    ("projects", "cmc projects"),
    ("packet", 'cmc packet --mission TEST --action "post update" --target "x.com" --object "exact post text" --proof "proof.png" --risk "public social" --why "testing approval flow" --stop "after one post"'),
]
quick_reference = "\n".join(
    f"{label}: {command}"
    for label, command in quick_commands
)

doc = f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Codex Mission Control</title>
<style>
  :root {{
    color-scheme: dark;
    --bg: #080808;
    --text: #f4f4f5;
    --muted: #9ca3af;
    --line: #2a2a2a;
    --surface: #111111;
    --soft: #171717;
    --green: #8ff7d2;
    --yellow: #f3d36a;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", Inter, Arial, sans-serif;
    letter-spacing: 0;
  }}
  main {{
    width: min(980px, calc(100vw - 40px));
    margin: 0 auto;
    padding: 34px 0 42px;
  }}
  header {{
    display: flex;
    justify-content: space-between;
    gap: 18px;
    align-items: flex-start;
    padding-bottom: 22px;
    border-bottom: 1px solid var(--line);
  }}
  h1 {{
    margin: 0 0 8px;
    font-size: 28px;
    line-height: 1.1;
    font-weight: 700;
  }}
  p {{
    margin: 0;
    color: var(--muted);
    line-height: 1.45;
    overflow-wrap: anywhere;
  }}
  .stamp {{
    color: var(--muted);
    font: 12px Menlo, Monaco, monospace;
    white-space: nowrap;
    margin-top: 4px;
  }}
  .primary {{
    display: grid;
    grid-template-columns: minmax(0, 1fr) 330px;
    gap: 18px;
    align-items: stretch;
    padding: 26px 0;
    border-bottom: 1px solid var(--line);
  }}
  .state {{
    min-height: 198px;
    display: flex;
    flex-direction: column;
    justify-content: center;
  }}
  .kicker {{
    color: var(--muted);
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    margin-bottom: 14px;
  }}
  .state h2 {{
    margin: 0;
    font-size: 46px;
    line-height: 1;
    font-weight: 750;
  }}
  .state strong {{
    display: block;
    margin-top: 12px;
    color: { 'var(--yellow)' if primary else 'var(--green)' };
    font-size: 20px;
    line-height: 1.25;
  }}
  .command {{
    background: #eeeeec;
    color: #111;
    border-radius: 8px;
    padding: 18px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    min-height: 198px;
  }}
  .command p {{ color: #404040; }}
  .command code {{
    display: block;
    margin: 18px 0;
    color: #111;
    font: 14px/1.45 Menlo, Monaco, monospace;
    overflow-wrap: anywhere;
  }}
  button {{
    appearance: none;
    border: 1px solid var(--line);
    border-radius: 8px;
    background: var(--surface);
    color: var(--text);
    width: 100%;
    min-height: 42px;
    text-align: left;
    cursor: pointer;
    padding: 10px 12px;
  }}
  .command button {{
    background: #111;
    color: #fff;
    border-color: #111;
    text-align: center;
    font-weight: 700;
  }}
  button span {{
    display: block;
    color: var(--muted);
    font-size: 12px;
    margin-bottom: 4px;
  }}
  button code {{
    color: inherit;
    font: 12px/1.35 Menlo, Monaco, monospace;
    overflow-wrap: anywhere;
  }}
  .content {{
    padding-top: 22px;
  }}
  section {{
    margin-bottom: 22px;
  }}
  h3, summary {{
    margin: 0 0 10px;
    color: var(--muted);
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }}
  td {{
    border-top: 1px solid var(--line);
    padding: 10px 8px;
    vertical-align: top;
  }}
  td:first-child {{
    width: 112px;
    color: var(--text);
    font-weight: 700;
  }}
  td:last-child {{
    color: var(--muted);
    overflow-wrap: anywhere;
  }}
  tr.clear td:last-child {{ color: var(--green); }}
  tr.held td:last-child {{ color: var(--yellow); }}
  details {{
    border-top: 1px solid var(--line);
    padding-top: 14px;
    margin-top: 14px;
  }}
  summary {{
    cursor: pointer;
    list-style: none;
  }}
  summary::-webkit-details-marker {{ display: none; }}
  pre {{
    margin: 8px 0 0;
    color: #d4d4d8;
    background: var(--soft);
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 12px;
    max-height: 220px;
    overflow: auto;
    white-space: pre-wrap;
    font: 12px/1.45 Menlo, Monaco, monospace;
  }}
  .meta {{
    display: flex;
    gap: 14px;
    flex-wrap: wrap;
    color: var(--muted);
    font-size: 13px;
    margin-top: 14px;
  }}
  .reference {{
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0 18px;
  }}
  @media (max-width: 820px) {{
    main {{ width: min(100vw - 28px, 980px); padding-top: 22px; }}
    header, .primary, .reference {{ display: block; }}
    .state, .command {{ min-height: 0; margin-bottom: 16px; }}
    .state h2 {{ font-size: 34px; }}
    .stamp {{ margin-top: 12px; }}
  }}
</style>
<main class="{esc(body_class)}">
  <header>
    <div>
      <h1>Mission Control</h1>
      <p title="{esc(hub)}">Local hub. Shared surfaces. Exact approvals.</p>
    </div>
    <div class="stamp">{esc(updated_at)}</div>
  </header>

  <div class="primary">
    <div class="state">
      <div class="kicker">{'Attention' if primary else 'Ready'}</div>
      <h2>{esc(main_label)}</h2>
      <strong>{esc(main_detail)}</strong>
    </div>
    <div class="command">
      <div>
        <p>{esc(main_note)}</p>
        <code>{esc(main_command)}</code>
      </div>
      <button data-copy="{esc(main_command)}">Copy command</button>
    </div>
  </div>

  <div class="meta">
    <span>{esc(mission_count)} missions</span>
    <span>{esc(locks)}</span>
    <span>Relay: {esc(relay)}</span>
    <span>{'Healthy' if ready else 'Needs check'}</span>
  </div>

  <div class="content">
    <section>
      <h3>Lanes</h3>
      <table>{lane_rows}</table>
    </section>
    <section>
      <h3>Missions</h3>
      <table>{project_rows}</table>
      {f'<p>{more_projects} more in <code>cmc projects</code>.</p>' if more_projects else ''}
    </section>

    <div class="reference">
      <details>
        <summary>Commands</summary>
        <pre>{esc(quick_reference)}</pre>
      </details>
      <details>
        <summary>Status</summary>
        <pre>{esc(cmc_status)}</pre>
      </details>
      <details>
        <summary>Doctor</summary>
        <pre>{esc(cmc_doctor)}</pre>
      </details>
      <details>
        <summary>Relay</summary>
        <pre>{esc(relay_status)}</pre>
      </details>
      <details>
        <summary>Approval packet</summary>
        <pre>{esc(cmc_packet)}</pre>
      </details>
    </div>
  </div>
</main>
<script>
  document.querySelectorAll("button[data-copy]").forEach((button) => {{
    button.addEventListener("click", async () => {{
      const original = button.textContent;
      try {{
        await navigator.clipboard.writeText(button.dataset.copy);
        button.textContent = "Copied";
      }} catch (_error) {{
        button.textContent = "Select manually";
      }}
      setTimeout(() => {{ button.textContent = original; }}, 1000);
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
