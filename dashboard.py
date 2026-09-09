"""Self-contained local dashboard, rendered directly from the selected hub."""

from __future__ import annotations

from datetime import datetime
import html
import math
import os
from pathlib import Path
import shlex
import tempfile
import time

import mission_control as mc


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def duration(seconds: float) -> str:
    seconds = max(0, seconds)
    if seconds < 60:
        return "<1m"
    if seconds < 3600:
        return f"{int(seconds // 60)}m"
    if seconds < 86400:
        return f"{int(seconds // 3600)}h {int(seconds % 3600 // 60)}m"
    return f"{int(seconds // 86400)}d"


def lease_detail(meta: dict[str, object], now: float) -> str:
    try:
        created = float(meta.get("created_epoch", 0))
        ttl = float(meta.get("ttl_seconds", -1))
    except (TypeError, ValueError, OverflowError):
        return "Expiry unknown"
    if not math.isfinite(created) or not math.isfinite(ttl) or created <= 0 or ttl < 0:
        return "Expiry unknown"
    if ttl == 0:
        return "No expiry"
    remaining = created + ttl - now
    try:
        expiry = datetime.fromtimestamp(created + ttl).astimezone().strftime("%d %b %Y · %H:%M %Z")
    except (ValueError, OverflowError, OSError):
        return "Expiry unknown"
    return f"Expired {expiry}" if remaining < 0 else f"Expires {expiry}"


def render_dashboard(hub: Path) -> str:
    hub = hub.expanduser().resolve()
    now = time.time()
    stamp = datetime.fromtimestamp(now).astimezone().strftime("%d %b %Y · %H:%M %Z")
    locks = dict(mc.lock_status(hub))
    missions = mc.load_missions(hub)
    command_prefix = [str(mc.ROOT / "cmc"), "--hub", str(hub)]

    def command(*args: str) -> str:
        return shlex.join(command_prefix + list(args))

    def copy_button(value: str, label: str = "Copy command", style: str = "") -> str:
        return f'<button type="button" class="copy {style}" data-copy="{esc(value)}">{esc(label)}</button>'

    lane_rows, options = [], []
    active = stale = unknown = 0
    abbreviations = ["BR", "GH", "EM", "SO", "CO", "DT", "GW"]
    for lane, abbreviation in zip(mc.DEFAULT_LANES, abbreviations):
        meta = locks.get(lane)
        state, label, owner, reason, lease = "clear", "Clear", "Unclaimed", "No claim recorded", "—"
        if meta is not None:
            owner = str(meta.get("owner") or "Unknown owner")
            reason = str(meta.get("reason") or "No reason recorded")
            lease = lease_detail(meta, now)
            if not str(meta.get("owner") or "").strip() or lease == "Expiry unknown":
                state, label = "unknown", "Check state"
                unknown += 1
            elif mc.lock_meta_is_stale(meta):
                state, label = "stale", "Stale"
                stale += 1
            else:
                state, label = "held", "In use"
                active += 1
        if state == "clear":
            detail = '<p>Choose this lane in the command composer. Use a unique owner for this session.</p>'
        elif state == "unknown":
            detail = (f'<p>Ownership or expiry could not be read. Inspect <code>{esc(mc.lock_root(hub) / lane / "lock.json")}</code> '
                      'before repairing this claim. It remains held.</p>')
        else:
            guidance = ("The lease expired. Check that the previous session has stopped before claiming again."
                        if state == "stale" else "Coordinate with the current owner. Release only when that session has finished.")
            release = command("release", lane, owner)
            detail = f'<p>{guidance}</p><div class="command-line"><code>{esc(release)}</code>{copy_button(release, "Copy release")}</div>'
        lane_rows.append(f'''<details class="lane" data-lane-state="{state}">
          <summary><span class="lane-symbol">{abbreviation}</span>
            <span class="lane-name">{esc(lane.replace('_', ' ').title())}<small>{esc(lane)}</small></span>
            <span class="lane-owner">{esc(owner)}<small>{esc(reason)}</small></span>
            <span class="lane-state"><span class="badge {state}">{label}</span><small>{esc(lease)}</small></span>
            <span class="expand" aria-hidden="true">+</span></summary><div class="lane-detail">{detail}</div></details>''')
        disabled = ' disabled' if state in {"held", "unknown"} else ''
        options.append(f'<option value="{lane}" data-state="{state}"{disabled}>{esc(lane.replace("_", " ").title())} · {label}</option>')

    clear = len(mc.DEFAULT_LANES) - len(locks)
    review = stale + unknown
    mission_rows = []
    broken = 0
    for item in missions:
        call = str(item.get("call_sign") or "MISSION")
        name = str(item.get("name") or call)
        path = str(item.get("path") or "")
        missing = not Path(str(item.get("link") or path)).exists() if path else True
        broken += int(missing)
        outbox = mc.outbox_dir(hub) / f"{call}.md"
        try:
            outbox_age = now - outbox.stat().st_mtime
            update = "Outbox · " + datetime.fromtimestamp(outbox.stat().st_mtime).astimezone().strftime("%d %b %Y · %H:%M %Z")
            old = outbox_age > 48 * 3600
        except OSError:
            update, old = "No outbox yet", False
        mission_rows.append(f'''<article class="mission" data-search="{esc((call + ' ' + name + ' ' + path).lower())}">
          <span class="call-sign">{esc(call)}</span><div class="mission-name"><h3>{esc(name)}</h3><p>{esc(path)}</p></div>
          <div class="mission-meta"><span class="{'attention-text' if missing or old else ''}">{'Project unavailable' if missing else esc(update)}</span>
          {copy_button(path, "Copy path")}</div></article>''')
    if not missions:
        mission_rows.append('<div class="empty"><h3>No missions yet</h3><p>Discover a project to add its folder and handoff outbox here.</p>'
                            + copy_button(command("discover"), "Copy discovery command") + '</div>')

    missing_ops = [name for name in mc.REQUIRED_OPS_FILES if not (mc.ops_dir(hub) / name).exists()]
    health = "Needs attention" if missing_ops or broken else "Healthy"
    health_detail = (f"{len(missing_ops)} missing hub files · {broken} unavailable projects"
                     if missing_ops or broken else "Hub files and project links are in place.")
    if review:
        title, description = "Codex Sessions", f"{review} lane{'s need' if review != 1 else ' needs'} a review. Confirm the previous session has stopped before reclaiming."
    elif active:
        title, description = "Codex Sessions", f"{active} lane{'s are' if active != 1 else ' is'} in use. {clear} remain clear for another session."
    else:
        title, description = "Codex Sessions", "All shared surfaces are clear. Claim a lane before starting shared work."

    css = (mc.ROOT / "assets" / "dashboard.css").read_text()
    js = (mc.ROOT / "assets" / "dashboard.js").read_text()
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light"><link rel="icon" href="data:,">
<title>Codex Sessions</title><style>{css}</style></head><body>
<a class="skip-link" href="#overview">Skip to workspace</a>
<aside class="sidebar"><a class="brand" href="#overview"><span class="brand-mark" aria-hidden="true">⌘</span><span>CODEX<br>SESSIONS</span></a>
<div class="workspace-label">LOCAL WORKSPACE</div><nav aria-label="Workspace"><a href="#overview" class="current"><span>01</span> Overview</a><a href="#lanes"><span>02</span> Surface lanes</a><a href="#missions"><span>03</span> Missions</a><a href="#commands"><span>04</span> Commands</a></nav>
<div class="sidebar-bottom"><span class="local-dot"></span> On this machine<p>{esc(hub)}</p><span class="version">CMC / {mc.VERSION}</span></div></aside>
<main id="overview"><header class="topbar"><span>CODEX / WORKSPACE OVERVIEW</span><span class="snapshot-label"><span class="snapshot-dot"></span> Local snapshot</span></header>
<section class="intro"><div><h1>{title}</h1><p class="intro-description">{description}</p></div><div class="snapshot"><time datetime="{datetime.fromtimestamp(now).astimezone().isoformat()}">{esc(stamp)}</time>{copy_button(command('dashboard'), 'Copy refresh command', 'quiet')}<small>Static snapshot. States below are recorded at this time. Run the refresh command before acting.</small></div></section>
<section class="metrics" aria-label="Workspace totals"><div><span class="metric-label">Lanes in use</span><strong>{active:02}</strong><span>Owned by a session</span></div><div><span class="metric-label">Clear lanes</span><strong class="green-text">{clear:02}</strong><span>Available to claim</span></div><div class="{'metric-alert' if review else ''}"><span class="metric-label">Need review</span><strong>{review:02}</strong><span>{stale} stale · {unknown} unknown</span></div><div><span class="metric-label">Missions</span><strong>{len(missions):02}</strong><span>Projects in this hub</span></div></section>
<div class="workspace-grid"><section class="panel lane-panel" id="lanes"><div class="section-heading"><div><p class="eyebrow">COORDINATION</p><h2>Surface lanes <span class="count">07</span></h2></div><span class="section-note">One owner per surface</span></div>
<div class="filters" role="group" aria-label="Filter lanes"><button data-filter="all" aria-pressed="true">All lanes</button><button data-filter="held" aria-pressed="false">In use</button><button data-filter="review" aria-pressed="false">Needs review</button><span id="lane-count" role="status">7 lanes</span></div>
<div class="lane-list">{''.join(lane_rows)}</div><p id="lane-empty" class="empty" hidden>No lanes match this view.</p><p class="panel-footnote">Claims coordinate local sessions. They do not grant permissions or stop an agent when a lease expires.</p></section>
<aside class="action-column"><section class="panel composer" id="commands"><p class="eyebrow">NEXT ACTION</p><h2>Claim a lane</h2><p class="panel-description">Build a command for your session, then run it in your terminal.</p>
<form id="claim-form" data-prefix="{esc(shlex.join(command_prefix))}"><label for="claim-lane">Surface</label><select id="claim-lane">{''.join(options)}</select><div class="form-row"><div><label for="claim-owner">Session owner</label><input id="claim-owner" placeholder="e.g. DESIGN-02" required autocomplete="off"></div><div><label for="claim-ttl">Lease (seconds)</label><input id="claim-ttl" type="number" min="0" step="1" value="1800" required></div></div><label for="claim-reason">What are you doing?</label><input id="claim-reason" value="Reviewing this project" required autocomplete="off"><p class="field-help">Use a unique owner. A lease of 0 has no expiry.</p><label class="sr-only" for="claim-command">Generated claim command</label><textarea id="claim-command" readonly rows="4" spellcheck="false" placeholder="Enter a session owner to build your command."></textarea><button class="primary-button" id="copy-claim" type="button">Copy claim command <span aria-hidden="true">↗</span></button><p id="claim-help" class="field-help" role="status"></p></form></section>
<section class="panel health"><div class="health-title"><h2>Hub check</h2><span class="badge {'unknown' if missing_ops or broken else 'clear'}">{health}</span></div><p>{esc(health_detail)}</p><div class="relay-line"><span>Optional Relay</span><strong>{esc(mc.relay_state())}</strong></div>{copy_button(command('doctor'), 'Copy health check', 'quiet')}</section></aside></div>
<section class="panel missions-panel" id="missions"><div class="section-heading"><div><p class="eyebrow">PROJECT INDEX</p><h2>Missions <span class="count">{len(missions):02}</span></h2></div><div class="mission-tools"><label class="sr-only" for="mission-search">Search missions</label><input id="mission-search" type="search" placeholder="Search missions…">{copy_button(command('discover'), 'Copy discover command', 'quiet')}</div></div><div class="mission-list">{''.join(mission_rows)}</div><p id="mission-empty" class="empty" role="status" hidden>No missions match your search.</p></section>
<section class="reference"><details><summary>Approval packet <span>Prepare the exact action for review</span></summary><pre>{esc(mc.packet_text())}</pre>{copy_button(command('packet'), 'Copy packet command')}</details><details><summary>Handoffs <span>Merge mission outboxes</span></summary><p>Write session updates to the mission outbox, then merge them into the global dashboard.</p><code>{esc(mc.outbox_dir(hub))}</code>{copy_button(command('merge'), 'Copy merge command')}</details></section>
<footer><span>Cooperative session locks</span><span>Snapshot only · Regenerate with <code>cmc dashboard</code></span></footer></main>
<dialog id="copy-dialog"><h2>Copy command</h2><p>Automatic copying is unavailable. Select and copy the text below.</p><textarea id="manual-copy" readonly rows="5" aria-label="Text to copy"></textarea><button id="close-copy" type="button">Done</button></dialog><div id="copy-status" class="toast" role="status" aria-live="polite"></div>
<script>{js}</script></body></html>'''


def write_dashboard(hub: Path) -> Path:
    hub = hub.expanduser().resolve()
    output = mc.ops_dir(hub) / "dashboard.html"
    source = render_dashboard(hub)
    # A second generation cannot truncate a page the browser is reading.
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent,
                                     prefix=".dashboard-", delete=False) as pending:
        pending_path = Path(pending.name)
        try:
            pending.write(source)
            pending.flush()
            os.chmod(pending_path, 0o600)
            os.replace(pending_path, output)
        finally:
            pending_path.unlink(missing_ok=True)
    return output
