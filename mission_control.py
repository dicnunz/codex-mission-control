#!/usr/bin/env python3
"""Codex Mission Control: local mission hub for Codex projects."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parent
TEMPLATE_ROOT = ROOT / "templates" / "mission-control"
VERSION = "0.2.4"
STARTER_BUNDLE_URL = "https://nicdunz.gumroad.com/l/agent-operator-starter-bundle"
SUPPORT_RECEIPT_URL = "https://nicdunz.gumroad.com/l/smrimu"
DEFAULT_HUB = Path(
    os.environ.get("CODEX_MISSION_CONTROL_HOME", "~/Codex Mission Control")
).expanduser()
DEFAULT_LANES = [
    "BROWSER",
    "GITHUB",
    "EMAIL",
    "PUBLIC_SOCIAL",
    "COMMERCE",
    "DESKTOP",
    "GLOBAL_WRITE",
]
REQUIRED_OPS_FILES = [
    "COMMAND_CENTER.md",
    "CODEX_OPERATING_SPEC.md",
    "RUNWAY_PROTOCOL.md",
    "SURFACE_LANES.md",
    "GLOBAL_DASHBOARD.md",
    "GO_NO_GO.md",
    "TASK_BOARD.md",
    "EVENT_LOG.md",
    "MISSION_STATE.md",
]
PRIMARY_PROJECT_MARKERS = {
    ".git",
    "AGENTS.md",
    "package.json",
    "pyproject.toml",
    "Cargo.toml",
    "go.mod",
    "Gemfile",
    "composer.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "requirements.txt",
}
SECONDARY_PROJECT_MARKERS = {
    "README.md",
    "Makefile",
}
AGENTS_MARKER_BEGIN = "<!-- codex-mission-control:start -->"
AGENTS_MARKER_END = "<!-- codex-mission-control:end -->"


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def display_path(path: Path) -> str:
    try:
        return str(path.expanduser().resolve())
    except FileNotFoundError:
        return str(path.expanduser())


def ops_dir(hub: Path) -> Path:
    return hub / "_ops"


def missions_dir(hub: Path) -> Path:
    return hub / "missions"


def outbox_dir(hub: Path) -> Path:
    return ops_dir(hub) / "CONSOLE_OUTBOX"


def lock_root(hub: Path) -> Path:
    return ops_dir(hub) / ".surface_locks"


def missions_path(hub: Path) -> Path:
    return ops_dir(hub) / "missions.json"


def read_json(path: Path, default: object) -> object:
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def template_vars(hub: Path) -> dict[str, str]:
    lane_rows = "\n".join(
        f"| `{lane}` | Clear | None | Safe local prep and drafts | External/account-changing action without approval |"
        for lane in DEFAULT_LANES
    )
    return {
        "HUB": display_path(hub),
        "UPDATED_AT": now_iso(),
        "LANE_ROWS": lane_rows,
        "LANES": ", ".join(DEFAULT_LANES),
    }


def render_template(text: str, values: dict[str, str]) -> str:
    rendered = text
    for key, value in values.items():
        rendered = rendered.replace("{{" + key + "}}", value)
    return rendered


def copy_templates(hub: Path) -> list[Path]:
    values = template_vars(hub)
    created: list[Path] = []
    for src in sorted(TEMPLATE_ROOT.rglob("*")):
        if src.is_dir():
            continue
        rel = src.relative_to(TEMPLATE_ROOT)
        dst = hub / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            continue
        dst.write_text(render_template(src.read_text(), values))
        created.append(dst)
    return created


def init_hub(hub: Path = DEFAULT_HUB) -> str:
    hub = hub.expanduser()
    (hub / "_ops" / "CONSOLE_OUTBOX").mkdir(parents=True, exist_ok=True)
    (hub / "missions").mkdir(parents=True, exist_ok=True)
    (hub / "templates").mkdir(parents=True, exist_ok=True)
    created = copy_templates(hub)
    if not missions_path(hub).exists():
        write_json(missions_path(hub), {"missions": []})
    return "\n".join(
        [
            "Mission Control initialized.",
            f"hub: {display_path(hub)}",
            f"created files: {len(created)}",
            "next: cmc discover",
            "optional support: cmc support",
        ]
    )


def likely_project(path: Path) -> bool:
    if not path.is_dir() or path.name.startswith("."):
        return False
    if any((path / marker).exists() for marker in PRIMARY_PROJECT_MARKERS):
        return True
    if not any((path / marker).exists() for marker in SECONDARY_PROJECT_MARKERS):
        return False
    visible_code = [
        item
        for item in path.iterdir()
        if item.name not in {".git", "__pycache__", "node_modules", "dist", "build"}
        and not item.name.startswith(".")
        and (item.is_file() or item.is_dir())
    ]
    return len(visible_code) >= 3


def discovery_roots(extra_roots: Iterable[str] = (), include_defaults: bool = True) -> list[Path]:
    roots = []
    if include_defaults:
        roots.extend(
            [
                Path.home() / "Developer",
                Path.home() / "Projects",
                Path.home() / "Documents" / "Codex",
                Path.cwd(),
            ]
        )
    roots.extend(Path(item).expanduser() for item in extra_roots)
    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        try:
            key = str(root.resolve())
        except FileNotFoundError:
            key = str(root)
        if key not in seen:
            seen.add(key)
            unique.append(root)
    return unique


def project_candidates(roots: Iterable[Path], hub: Path) -> list[Path]:
    candidates: list[Path] = []
    hub_resolved = hub.expanduser().resolve() if hub.exists() else hub.expanduser()
    for root in roots:
        root = root.expanduser()
        if not root.exists() or not root.is_dir():
            continue
        scan = [root] if likely_project(root) else []
        try:
            scan.extend(item for item in root.iterdir() if item.is_dir())
        except OSError:
            continue
        for item in scan:
            try:
                resolved = item.resolve()
            except FileNotFoundError:
                continue
            if resolved == hub_resolved or hub_resolved in resolved.parents:
                continue
            if likely_project(resolved) and resolved not in candidates:
                candidates.append(resolved)
    return sorted(candidates, key=lambda item: str(item).lower())


def words_for_name(name: str) -> list[str]:
    return [part for part in re.split(r"[^A-Za-z0-9]+", name) if part]


def base_call_sign(path: Path) -> str:
    words = words_for_name(path.name)
    if len(words) >= 2:
        sign = "".join(word[0] for word in words[:4])
    elif words:
        sign = words[0][:8]
    else:
        sign = "MISSION"
    sign = re.sub(r"[^A-Za-z0-9]", "", sign).upper()
    return sign or "MISSION"


def mission_slug(path: Path) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", path.name).strip("-").lower()
    return slug or "project"


def load_missions(hub: Path) -> list[dict[str, str]]:
    data = read_json(missions_path(hub), {"missions": []})
    if not isinstance(data, dict):
        return []
    missions = data.get("missions", [])
    return missions if isinstance(missions, list) else []


def save_missions(hub: Path, missions: list[dict[str, str]]) -> None:
    write_json(missions_path(hub), {"missions": missions})


def unique_call_sign(path: Path, existing: list[dict[str, str]]) -> str:
    used = {str(item.get("call_sign", "")).upper() for item in existing}
    base = base_call_sign(path)
    sign = base
    index = 2
    while sign in used or sign == "FLIGHT":
        sign = f"{base}{index}"
        index += 1
    return sign


def discover_projects(
    hub: Path = DEFAULT_HUB,
    roots: Iterable[str] = (),
    include_defaults: bool = True,
) -> str:
    init_hub(hub)
    hub = hub.expanduser()
    existing = load_missions(hub)
    existing_paths = {str(Path(item.get("path", "")).expanduser()) for item in existing}
    added: list[dict[str, str]] = []
    for project in project_candidates(discovery_roots(roots, include_defaults), hub):
        project_key = str(project)
        if project_key in existing_paths:
            continue
        call_sign = unique_call_sign(project, existing + added)
        link_name = f"{call_sign}-{mission_slug(project)}"
        link = missions_dir(hub) / link_name
        if not link.exists():
            try:
                link.symlink_to(project, target_is_directory=True)
            except OSError:
                link.mkdir(parents=True, exist_ok=True)
                (link / "PROJECT_PATH.txt").write_text(str(project) + "\n")
        outbox = outbox_dir(hub) / f"{call_sign}.md"
        if not outbox.exists():
            outbox.write_text(
                f"# {call_sign} Outbox\n\n"
                "Write mission updates here for FLIGHT to merge.\n\n"
                "## Template\n\n"
                "- Status:\n"
                "- Material files changed:\n"
                "- Pending approval packet:\n"
                "- External surface needed:\n"
                "- Conflict risk:\n"
                "- Requested FLIGHT merge/update:\n"
            )
        item = {
            "name": project.name,
            "call_sign": call_sign,
            "path": str(project),
            "link": str(link),
            "created_at": now_iso(),
        }
        added.append(item)
        existing_paths.add(project_key)
    if added:
        existing.extend(added)
        save_missions(hub, existing)
    lines = [
        "Project discovery complete.",
        f"hub: {display_path(hub)}",
        f"added: {len(added)}",
    ]
    if added:
        lines.extend(f"- {item['call_sign']}: {item['path']}" for item in added[:12])
        if len(added) > 12:
            lines.append(f"- ... {len(added) - 12} more")
    else:
        lines.append("No new projects found. Add a repo under ~/Developer, ~/Projects, ~/Documents/Codex, or run cmc discover /path/to/project.")
    return "\n".join(lines)


def mission_instruction_block(mission: dict[str, str], hub: Path) -> str:
    call_sign = str(mission.get("call_sign") or "MISSION").upper()
    name = str(mission.get("name") or "this project")
    return "\n".join(
        [
            AGENTS_MARKER_BEGIN,
            f"# Codex Mission Control: {call_sign}",
            "",
            f"You are `{call_sign}`, the Codex mission console for `{name}`.",
            "",
            "## Source Of Truth",
            "",
            f"- Mission Control hub: `{display_path(hub)}`",
            f"- Mission outbox: `{display_path(outbox_dir(hub) / (call_sign + '.md'))}`",
            "",
            "## Codex Mission Contract",
            "",
            "- Start with the concrete outcome required this turn.",
            "- Use the Mission Control operating shape: role, objective, hard rules, tool gates, validation, and terse output.",
            "- Read only the hub files needed to ground the work: `COMMAND_CENTER.md`, `CODEX_OPERATING_SPEC.md`, `RUNWAY_PROTOCOL.md`, `SURFACE_LANES.md`, and `GO_NO_GO.md`.",
            "- Use tools when they materially improve correctness; do not stop before required verification passes.",
            "- Keep local edits narrow and project-native.",
            "- Before touching a shared surface, claim the matching lane with `cmc claim`.",
            "- Before public, outreach, account, payment, destructive, or reputational action, prepare an exact approval packet and stop.",
            "- Final replies should say what changed, what was verified, and the exact blocker if anything remains blocked.",
            AGENTS_MARKER_END,
        ]
    )


def replace_or_append_agents(existing: str, block: str) -> str:
    if AGENTS_MARKER_BEGIN in existing and AGENTS_MARKER_END in existing:
        pattern = re.compile(
            re.escape(AGENTS_MARKER_BEGIN) + r".*?" + re.escape(AGENTS_MARKER_END),
            re.DOTALL,
        )
        return pattern.sub(block, existing).rstrip() + "\n"
    if existing.strip():
        return existing.rstrip() + "\n\n" + block + "\n"
    return block + "\n"


def adopt_agents(hub: Path = DEFAULT_HUB, write: bool = False) -> str:
    hub = hub.expanduser()
    missions = load_missions(hub)
    if not missions:
        return "No missions found. Run cmc discover first."
    changed = 0
    skipped = 0
    lines = ["Mission instruction adoption:"]
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    for mission in missions:
        project = Path(str(mission.get("path") or "")).expanduser()
        if not project.is_dir():
            skipped += 1
            lines.append(f"- skip {mission.get('call_sign')}: missing project folder")
            continue
        agents = project / "AGENTS.md"
        block = mission_instruction_block(mission, hub)
        existing = agents.read_text() if agents.exists() else ""
        updated = replace_or_append_agents(existing, block)
        if updated == existing:
            skipped += 1
            lines.append(f"- ok {mission.get('call_sign')}: already current")
            continue
        changed += 1
        if write:
            if agents.exists():
                backup = agents.with_name(f"AGENTS.md.cmc-backup-{stamp}")
                backup.write_text(existing)
            agents.write_text(updated)
            lines.append(f"- wrote {mission.get('call_sign')}: {agents}")
        else:
            action = "update" if agents.exists() else "create"
            lines.append(f"- would {action} {mission.get('call_sign')}: {agents}")
    mode = "wrote" if write else "dry run"
    lines.insert(1, f"mode: {mode}; changed: {changed}; skipped: {skipped}")
    if not write and changed:
        lines.append("Apply with: cmc adopt --write")
    return "\n".join(lines)


def instructions_text(hub: Path = DEFAULT_HUB) -> str:
    init_hub(hub)
    agents = hub.expanduser() / "AGENTS.md"
    return agents.read_text()


def read_lock_meta(path: Path) -> dict[str, object]:
    data = read_json(path / "lock.json", {})
    return data if isinstance(data, dict) else {}


def lock_is_stale(path: Path, ttl: int) -> bool:
    meta = read_lock_meta(path)
    created = float(meta.get("created_epoch", 0) or 0)
    return ttl > 0 and created > 0 and time.time() - created > ttl


def lock_meta_is_stale(meta: dict[str, object]) -> bool:
    ttl = int(float(meta.get("ttl_seconds", 0) or 0))
    created = float(meta.get("created_epoch", 0) or 0)
    return ttl > 0 and created > 0 and time.time() - created > ttl


def valid_lane(lane: str) -> str:
    normalized = lane.strip().upper()
    if normalized not in DEFAULT_LANES:
        raise ValueError(f"invalid lane: {lane}. valid lanes: {', '.join(DEFAULT_LANES)}")
    return normalized


def claim_lane(hub: Path, lane: str, owner: str, reason: str, ttl: int = 1800) -> tuple[int, str]:
    init_hub(hub)
    lane = valid_lane(lane)
    root = lock_root(hub)
    root.mkdir(parents=True, exist_ok=True)
    path = root / lane
    if path.exists() and lock_is_stale(path, ttl):
        shutil.rmtree(path)
    try:
        path.mkdir()
    except FileExistsError:
        return 1, "held: " + lane + "\n" + json.dumps(read_lock_meta(path), indent=2, sort_keys=True)
    meta = {
        "lane": lane,
        "owner": owner,
        "reason": reason,
        "created_at": now_iso(),
        "created_epoch": time.time(),
        "pid": os.getpid(),
        "ttl_seconds": ttl,
    }
    write_json(path / "lock.json", meta)
    return 0, f"acquired: {lane} by {owner}"


def release_lane(hub: Path, lane: str, owner: str) -> tuple[int, str]:
    lane = valid_lane(lane)
    path = lock_root(hub) / lane
    if not path.exists():
        return 0, f"not held: {lane}"
    meta = read_lock_meta(path)
    current_owner = str(meta.get("owner", ""))
    if current_owner and current_owner != owner:
        return 1, f"not owner: {lane} held by {current_owner}"
    shutil.rmtree(path)
    return 0, f"released: {lane}"


def lock_status(hub: Path) -> list[tuple[str, dict[str, object]]]:
    root = lock_root(hub)
    if not root.exists():
        return []
    return [
        (path.name, read_lock_meta(path))
        for path in sorted(root.iterdir())
        if path.is_dir()
    ]


def relay_state() -> str:
    runtime_root = Path(
        os.environ.get(
            "CODEX_RELAY_RUNTIME_DIR",
            str(Path.home() / "Library" / "Application Support" / "CodexRelay"),
        )
    ).expanduser()
    runtime = runtime_root / "codex_relay.py"
    runtime_env = runtime_root / ".env"
    repo_env = ROOT / ".env"
    label = os.environ.get("CODEX_RELAY_LABEL", "com.codexrelay.agent")
    running = "unknown"
    if sys.platform == "darwin":
        result = subprocess.run(
            ["launchctl", "print", f"gui/{os.getuid()}/{label}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
            check=False,
        )
        running = "running" if result.returncode == 0 and ("state = running" in result.stdout or "pid = " in result.stdout) else "not running"
    if runtime.exists() and runtime_env.exists():
        return f"installed, {running}"
    if repo_env.exists() or runtime_env.exists():
        return "configured, launchagent missing"
    return "not installed"


def status_text(hub: Path = DEFAULT_HUB) -> str:
    hub = hub.expanduser()
    missions = load_missions(hub)
    missing = [name for name in REQUIRED_OPS_FILES if not (ops_dir(hub) / name).exists()]
    locks = lock_status(hub)
    stale_locks = [(lane, meta) for lane, meta in locks if lock_meta_is_stale(meta)]
    stale_outboxes: list[str] = []
    if outbox_dir(hub).exists():
        cutoff = time.time() - 48 * 3600
        for path in sorted(outbox_dir(hub).glob("*.md")):
            if path.stat().st_mtime < cutoff:
                stale_outboxes.append(path.name)
    lines = [
        "Codex Mission Control status",
        f"hub: {display_path(hub)}",
        f"hub files: {'ok' if not missing else 'missing ' + ', '.join(missing)}",
        f"missions: {len(missions)}",
        f"locks: {len(locks)} held" + (f", {len(stale_locks)} stale" if stale_locks else ""),
        f"stale outboxes: {len(stale_outboxes)}",
        f"relay: {relay_state()}",
    ]
    if missions:
        lines.extend(f"- {item.get('call_sign')}: {item.get('name')} -> {item.get('path')}" for item in missions[:8])
        if len(missions) > 8:
            lines.append(f"- ... {len(missions) - 8} more")
    else:
        lines.append("No missions yet. Run cmc discover.")
    if locks:
        lines.append("Held lanes:")
        lines.extend(
            f"- {lane}: {meta.get('owner')} ({meta.get('reason')})"
            + (" [stale]" if lock_meta_is_stale(meta) else "")
            for lane, meta in locks
        )
    return "\n".join(lines)


def lanes_text(hub: Path = DEFAULT_HUB) -> str:
    locks = dict(lock_status(hub))
    lines = ["Surface lanes:"]
    for lane in DEFAULT_LANES:
        meta = locks.get(lane)
        if meta:
            suffix = " [stale]" if lock_meta_is_stale(meta) else ""
            lines.append(f"- {lane}: held by {meta.get('owner')} ({meta.get('reason')}){suffix}")
        else:
            lines.append(f"- {lane}: clear")
    return "\n".join(lines)


def projects_text(hub: Path = DEFAULT_HUB) -> str:
    missions = load_missions(hub.expanduser())
    if not missions:
        return "Projects: none. Run cmc discover."
    lines = ["Projects:"]
    lines.extend(f"- {item.get('call_sign')}: {item.get('name')} -> {item.get('path')}" for item in missions)
    return "\n".join(lines)


def doctor_text(hub: Path = DEFAULT_HUB) -> str:
    hub = hub.expanduser()
    missing = [name for name in REQUIRED_OPS_FILES if not (ops_dir(hub) / name).exists()]
    missions = load_missions(hub)
    broken_links = [
        str(item.get("link"))
        for item in missions
        if item.get("link") and not Path(str(item["link"])).exists()
    ]
    template_ok = TEMPLATE_ROOT.exists() and any(TEMPLATE_ROOT.rglob("*.md"))
    locks = lock_status(hub)
    stale_locks = [(lane, meta) for lane, meta in locks if lock_meta_is_stale(meta)]
    lines = [
        "Codex Mission Control doctor",
        f"version: {VERSION}",
        f"hub: {display_path(hub)}",
        f"templates: {'ok' if template_ok else 'missing'}",
        f"ops files: {'ok' if not missing else 'missing ' + ', '.join(missing)}",
        f"missions: {len(missions)}",
        f"broken mission links: {len(broken_links)}",
        f"locks: {len(locks)} held" + (f", {len(stale_locks)} stale" if stale_locks else ""),
        f"relay: {relay_state()}",
    ]
    if broken_links:
        lines.extend(f"- broken: {link}" for link in broken_links[:8])
    if stale_locks:
        lines.extend(f"- stale lock: {lane} held by {meta.get('owner')}" for lane, meta in stale_locks[:8])
    return "\n".join(lines)


def packet_text(
    mission: str = "MISSION",
    action: str = "exact action",
    target: str = "exact target",
    object_text: str = "exact text/change/object",
    proof: str = "proof path after execution",
    risk: str = "risk flags",
    reason: str = "why this matters now",
    stop: str = "stop condition",
) -> str:
    return "\n".join(
        [
            f"# {mission.upper()} Approval Packet",
            "",
            f"- Mission: {mission.upper()}",
            f"- Exact action: {action}",
            f"- Target: {target}",
            f"- Exact text/change/object: {object_text}",
            f"- Evidence checked: current local mission files and live surface state must be rechecked before execution",
            f"- Risk flags: {risk}",
            f"- Why now: {reason}",
            f"- Proof after execution: {proof}",
            f"- Stop condition: {stop}",
        ]
    )


def merge_outboxes(hub: Path = DEFAULT_HUB) -> str:
    init_hub(hub)
    hub = hub.expanduser()
    dashboard = ops_dir(hub) / "GLOBAL_DASHBOARD.md"
    chunks = []
    for path in sorted(outbox_dir(hub).glob("*.md")):
        text = path.read_text().strip()
        if text:
            chunks.append(f"## {path.stem}\n\n{text}\n")
    merged = [
        "# Global Dashboard",
        "",
        f"Updated: {now_iso()}",
        "",
        "Mission outbox merge:",
        "",
        "\n".join(chunks).strip() if chunks else "No mission outbox updates yet.",
        "",
    ]
    dashboard.write_text("\n".join(merged))
    return f"merged outboxes: {len(chunks)}\ndashboard: {dashboard}"


def relay_install() -> int:
    return subprocess.call([sys.executable, str(ROOT / "scripts" / "configure.py")])


def dashboard_open(hub: Path, no_open: bool = False) -> int:
    init_hub(hub)
    env = os.environ.copy()
    env["CODEX_MISSION_CONTROL_HOME"] = str(hub.expanduser())
    command = [str(ROOT / "scripts" / "status_ui.sh")]
    if no_open:
        command.append("--no-open")
    return subprocess.call(command, env=env)


def support_text() -> str:
    return "\n".join(
        [
            "Codex Mission Control support",
            "",
            "If Mission Control saves you setup time, the smallest support path is:",
            SUPPORT_RECEIPT_URL,
            "",
            "If you want the broader operator templates, browser-agent lanes, proof ledgers,",
            "public-action gates, and handoff material, use the starter bundle:",
            STARTER_BUNDLE_URL,
        ]
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cmc", description="Codex Mission Control")
    parser.add_argument("--hub", default=str(DEFAULT_HUB), help="Mission Control hub folder")
    parser.add_argument("--version", action="version", version=f"cmc {VERSION}")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="initialize the local Mission Control hub")

    discover = sub.add_parser("discover", help="discover projects and create mission symlinks")
    discover.add_argument("roots", nargs="*", help="extra roots or project folders to scan")
    discover.add_argument(
        "--include-defaults",
        action="store_true",
        help="also scan ~/Developer, ~/Projects, ~/Documents/Codex, and the current directory",
    )

    sub.add_parser("status", help="show Mission Control status")
    sub.add_parser("doctor", help="check hub health")
    sub.add_parser("lanes", help="show surface lanes")
    sub.add_parser("projects", help="show discovered missions")
    sub.add_parser("instructions", help="print the Mission Control instructions")
    sub.add_parser("support", help="show optional paid support links")

    adopt = sub.add_parser("adopt", help="install Mission Control AGENTS.md blocks into discovered projects")
    adopt.add_argument("--write", action="store_true", help="write AGENTS.md blocks; default is dry-run")

    claim = sub.add_parser("claim", help="claim a shared surface lane")
    claim.add_argument("lane")
    claim.add_argument("owner")
    claim.add_argument("reason")
    claim.add_argument("--ttl", type=int, default=1800)

    release = sub.add_parser("release", help="release a shared surface lane")
    release.add_argument("lane")
    release.add_argument("owner")

    packet = sub.add_parser("packet", help="generate an exact approval packet")
    packet.add_argument("--mission", default="MISSION")
    packet.add_argument("--action", default="exact action")
    packet.add_argument("--target", default="exact target")
    packet.add_argument("--object", dest="object_text", default="exact text/change/object")
    packet.add_argument("--proof", default="proof path after execution")
    packet.add_argument("--risk", default="risk flags")
    packet.add_argument("--why", default="why this matters now")
    packet.add_argument("--stop", default="stop condition")

    sub.add_parser("merge", help="merge mission outboxes into the global dashboard")
    dashboard = sub.add_parser("dashboard", help="open the local Mission Control dashboard")
    dashboard.add_argument("--no-open", action="store_true", help="write the dashboard path without opening it")

    relay = sub.add_parser("relay", help="Mission Control Relay commands")
    relay_sub = relay.add_subparsers(dest="relay_command", required=True)
    relay_sub.add_parser("install", help="install the Telegram relay extension")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    hub = Path(args.hub).expanduser()
    try:
        if args.command == "init":
            print(init_hub(hub))
            return 0
        if args.command == "discover":
            print(discover_projects(hub, args.roots, include_defaults=args.include_defaults or not args.roots))
            return 0
        if args.command == "status":
            print(status_text(hub))
            return 0
        if args.command == "doctor":
            print(doctor_text(hub))
            return 0
        if args.command == "lanes":
            print(lanes_text(hub))
            return 0
        if args.command == "projects":
            print(projects_text(hub))
            return 0
        if args.command == "instructions":
            print(instructions_text(hub))
            return 0
        if args.command == "support":
            print(support_text())
            return 0
        if args.command == "adopt":
            print(adopt_agents(hub, args.write))
            return 0
        if args.command == "claim":
            code, text = claim_lane(hub, args.lane, args.owner, args.reason, args.ttl)
            print(text)
            return code
        if args.command == "release":
            code, text = release_lane(hub, args.lane, args.owner)
            print(text)
            return code
        if args.command == "packet":
            print(packet_text(args.mission, args.action, args.target, args.object_text, args.proof, args.risk, args.why, args.stop))
            return 0
        if args.command == "merge":
            print(merge_outboxes(hub))
            return 0
        if args.command == "dashboard":
            return dashboard_open(hub, args.no_open)
        if args.command == "relay" and args.relay_command == "install":
            return relay_install()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
