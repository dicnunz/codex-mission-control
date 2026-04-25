#!/bin/zsh
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
OUT="$ROOT/assets/codex-relay-demo.mp4"
POSTER="$ROOT/assets/codex-relay-demo-poster.png"
SOCIAL="$ROOT/assets/social-card.svg"
SOCIAL_PNG="$ROOT/assets/social-card.png"
TRANSCRIPT="$ROOT/assets/demo-transcript.svg"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

need() {
  command -v "$1" >/dev/null 2>&1 || {
    printf "missing required command: %s\n" "$1" >&2
    exit 1
  }
}

need sips
need ffmpeg

write_social() {
  cat > "$SOCIAL" <<'SVG'
<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="640" viewBox="0 0 1280 640" role="img" aria-label="Codex Relay social card">
  <rect width="1280" height="640" fill="#050505"/>
  <rect x="54" y="44" width="1172" height="552" rx="18" fill="#101010" stroke="#2b2b2b"/>
  <text x="104" y="122" fill="#f5f5f5" font-family="Arial, sans-serif" font-size="74" font-weight="700">Text your Mac. Codex works.</text>
  <text x="108" y="178" fill="#b8b8b8" font-family="Arial, sans-serif" font-size="28">Telegram is the remote. Your Mac runs local Codex.</text>
  <text x="108" y="226" fill="#f5f5f5" font-family="Arial, sans-serif" font-size="28">No VNC. No extra hosted relay server.</text>

  <g transform="translate(108 280)">
    <rect width="320" height="246" rx="28" fill="#050505" stroke="#303030"/>
    <rect x="24" y="26" width="272" height="42" rx="20" fill="#1f2937"/>
    <circle cx="48" cy="47" r="10" fill="#5eead4"/>
    <text x="70" y="54" fill="#f5f5f5" font-family="Arial, sans-serif" font-size="17" font-weight="700">Telegram DM</text>
    <rect x="34" y="92" width="236" height="38" rx="16" fill="#2563eb"/>
    <text x="54" y="117" fill="#ffffff" font-family="Menlo, monospace" font-size="15">make repo launch-ready</text>
    <rect x="82" y="148" width="204" height="58" rx="18" fill="#171717" stroke="#333333"/>
    <text x="102" y="174" fill="#d4d4d4" font-family="Menlo, monospace" font-size="14">done</text>
    <text x="102" y="194" fill="#22c55e" font-family="Menlo, monospace" font-size="14">tests passed</text>
  </g>

  <text x="476" y="414" fill="#d4d4d4" font-family="Arial, sans-serif" font-size="46" font-weight="700">-&gt;</text>

  <g transform="translate(562 258)">
    <rect width="560" height="278" rx="18" fill="#050505" stroke="#303030"/>
    <rect width="560" height="44" rx="18" fill="#1a1a1a"/>
    <circle cx="30" cy="22" r="6" fill="#ef4444"/>
    <circle cx="52" cy="22" r="6" fill="#f59e0b"/>
    <circle cx="74" cy="22" r="6" fill="#22c55e"/>
    <text x="34" y="86" fill="#a7f3d0" font-family="Menlo, monospace" font-size="17">$ codex exec</text>
    <text x="34" y="126" fill="#e5e5e5" font-family="Menlo, monospace" font-size="17">read repo state</text>
    <text x="34" y="160" fill="#e5e5e5" font-family="Menlo, monospace" font-size="17">edit files and run tests</text>
    <text x="34" y="194" fill="#e5e5e5" font-family="Menlo, monospace" font-size="17">final answer back to Telegram</text>
    <rect x="34" y="224" width="244" height="34" rx="17" fill="#f5f5f5"/>
    <text x="54" y="247" fill="#111111" font-family="Arial, sans-serif" font-size="15" font-weight="700">unofficial and local-first</text>
  </g>

  <text x="108" y="574" fill="#8b8b8b" font-family="Menlo, monospace" font-size="21">github.com/dicnunz/codex-relay</text>
</svg>
SVG
}

write_transcript() {
  cat > "$TRANSCRIPT" <<'SVG'
<svg xmlns="http://www.w3.org/2000/svg" width="960" height="640" viewBox="0 0 960 640" role="img" aria-label="Codex Relay Telegram transcript">
  <rect width="960" height="640" fill="#080808"/>
  <rect x="70" y="44" width="820" height="552" rx="24" fill="#111111" stroke="#2a2a2a"/>
  <text x="112" y="102" fill="#f5f5f5" font-family="Arial, sans-serif" font-size="30" font-weight="700">Codex Relay</text>
  <text x="112" y="134" fill="#8b8b8b" font-family="Arial, sans-serif" font-size="17">Telegram -&gt; LaunchAgent -&gt; Codex CLI -&gt; Mac</text>

  <g font-family="Menlo, monospace" font-size="17">
    <rect x="112" y="178" width="286" height="48" rx="18" fill="#2563eb"/>
    <text x="134" y="209" fill="#ffffff">/alive</text>

    <rect x="322" y="252" width="430" height="126" rx="20" fill="#171717" stroke="#333333"/>
    <text x="348" y="286" fill="#f5f5f5">Mac is live.</text>
    <text x="348" y="318" fill="#a7f3d0">configured model</text>
    <text x="348" y="350" fill="#a7f3d0">Telegram -&gt; Codex CLI</text>

    <rect x="112" y="420" width="286" height="48" rx="18" fill="#2563eb"/>
    <text x="134" y="451" fill="#ffffff">/policy</text>

    <rect x="322" y="500" width="454" height="58" rx="20" fill="#171717" stroke="#333333"/>
    <text x="348" y="536" fill="#f5f5f5">shows exactly where it stops</text>
  </g>
</svg>
SVG
}

write_frame() {
  local file="$1"
  local eyebrow="$2"
  local headline="$3"
  local sub="$4"
  local phone_a="$5"
  local phone_b="$6"
  local mac_a="$7"
  local mac_b="$8"
  local mac_c="$9"

  cat > "$file" <<SVG
<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <rect width="1280" height="720" fill="#050505"/>
  <text x="64" y="62" fill="#8b8b8b" font-family="Arial, sans-serif" font-size="18" font-weight="700">$eyebrow</text>
  <text x="64" y="126" fill="#f5f5f5" font-family="Arial, sans-serif" font-size="58" font-weight="700">$headline</text>
  <text x="68" y="172" fill="#b8b8b8" font-family="Arial, sans-serif" font-size="25">$sub</text>

  <g transform="translate(78 234)">
    <rect width="366" height="386" rx="30" fill="#050505" stroke="#303030" stroke-width="2"/>
    <rect x="24" y="28" width="318" height="48" rx="22" fill="#1f2937"/>
    <circle cx="56" cy="52" r="15" fill="#5eead4"/>
    <text x="84" y="58" fill="#f5f5f5" font-family="Arial, sans-serif" font-size="17" font-weight="700">Codex Relay</text>
    <rect x="40" y="112" width="286" height="42" rx="18" fill="#2563eb"/>
    <text x="62" y="140" fill="#ffffff" font-family="Menlo, monospace" font-size="16">$phone_a</text>
    <rect x="92" y="184" width="228" height="72" rx="18" fill="#171717" stroke="#333333"/>
    <text x="114" y="216" fill="#f5f5f5" font-family="Menlo, monospace" font-size="16">$phone_b</text>
    <rect x="40" y="296" width="286" height="42" rx="18" fill="#2563eb"/>
    <text x="62" y="324" fill="#ffffff" font-family="Menlo, monospace" font-size="16">go do the Mac task</text>
  </g>

  <text x="504" y="448" fill="#d4d4d4" font-family="Arial, sans-serif" font-size="54" font-weight="700">-&gt;</text>

  <g transform="translate(610 224)">
    <rect width="596" height="402" rx="24" fill="#050505" stroke="#303030" stroke-width="2"/>
    <rect width="596" height="48" rx="24" fill="#1a1a1a"/>
    <circle cx="32" cy="24" r="7" fill="#ef4444"/>
    <circle cx="56" cy="24" r="7" fill="#f59e0b"/>
    <circle cx="80" cy="24" r="7" fill="#22c55e"/>
    <text x="34" y="96" fill="#a7f3d0" font-family="Menlo, monospace" font-size="19">$ codex exec</text>
    <text x="34" y="148" fill="#f5f5f5" font-family="Menlo, monospace" font-size="19">$mac_a</text>
    <text x="34" y="194" fill="#f5f5f5" font-family="Menlo, monospace" font-size="19">$mac_b</text>
    <text x="34" y="240" fill="#f5f5f5" font-family="Menlo, monospace" font-size="19">$mac_c</text>
    <rect x="34" y="304" width="236" height="40" rx="20" fill="#f5f5f5"/>
    <text x="56" y="330" fill="#111111" font-family="Arial, sans-serif" font-size="17" font-weight="700">reply back to Telegram</text>
  </g>
</svg>
SVG
}

render_svg() {
  local svg="$1"
  local png="$2"
  sips -s format png "$svg" --out "$png" >/dev/null
}

write_social
write_transcript
render_svg "$SOCIAL" "$SOCIAL_PNG"

write_frame "$TMP/frame1.svg" \
  "CODEX RELAY" \
  "Text your Mac. Codex works." \
  "Telegram is the remote. The Mac still runs local Codex." \
  "make repo launch-ready" \
  "job 8f31c2a0" \
  "read repo state" \
  "edit files and run tests" \
  "reply when finished"

write_frame "$TMP/frame2.svg" \
  "INSTALL ONCE" \
  "A small local bridge." \
  "Redacted bot token, allowlist, LaunchAgent, doctor check." \
  "git clone" \
  "./scripts/install.sh" \
  "verify bot token" \
  "allowlist your DM" \
  "start LaunchAgent"

write_frame "$TMP/frame3.svg" \
  "FIRST CHECK" \
  "The phone sees the Mac." \
  "Fast commands prove the bridge before a long Codex run." \
  "/alive" \
  "Mac is live" \
  "route is healthy" \
  "model is configured" \
  "folder is known"

write_frame "$TMP/frame4.svg" \
  "REAL TASK" \
  "Send the work." \
  "Ask for a repo pass, a screenshot read, or a small fix." \
  "/cd Projects/app" \
  "active folder set" \
  "open Codex CLI" \
  "run in that folder" \
  "keep account context"

write_frame "$TMP/frame5.svg" \
  "MAC RUN" \
  "Codex works locally." \
  "Files, tools, sandbox, and approvals stay on the Mac." \
  "make this shippable" \
  "working..." \
  "inspect files" \
  "edit and test" \
  "summarize result"

write_frame "$TMP/frame6.svg" \
  "SCREENSHOTS" \
  "Ask what changed." \
  "Telegram images become private Codex image inputs." \
  "sent screenshot" \
  "image attached" \
  "save privately" \
  "pass with image" \
  "prune later"

write_frame "$TMP/frame7.svg" \
  "BOUNDARY" \
  "It says where it stops." \
  "No official claims. No MFA bypass. No hidden hosted relay." \
  "/policy" \
  "limits shown" \
  "allowlist only" \
  "local runtime" \
  "your Mac, your account"

write_frame "$TMP/frame8.svg" \
  "TRY IT" \
  "Text your Mac. Codex works." \
  "The first install path is the product." \
  "install feedback" \
  "first blocker?" \
  "run fresh clone test" \
  "open feedback issue" \
  "github.com/dicnunz/codex-relay"

for i in 1 2 3 4 5 6 7 8; do
  render_svg "$TMP/frame$i.svg" "$TMP/frame$i.png"
done

cp "$TMP/frame1.png" "$POSTER"

ffmpeg -y -v error \
  -loop 1 -t 6.0 -i "$TMP/frame1.png" \
  -loop 1 -t 6.2 -i "$TMP/frame2.png" \
  -loop 1 -t 6.0 -i "$TMP/frame3.png" \
  -loop 1 -t 6.8 -i "$TMP/frame4.png" \
  -loop 1 -t 7.0 -i "$TMP/frame5.png" \
  -loop 1 -t 6.4 -i "$TMP/frame6.png" \
  -loop 1 -t 6.8 -i "$TMP/frame7.png" \
  -loop 1 -t 6.8 -i "$TMP/frame8.png" \
  -filter_complex "[0:v]fps=30,fade=t=out:st=5.75:d=0.25[v0];[1:v]fps=30,fade=t=in:st=0:d=0.2,fade=t=out:st=5.95:d=0.25[v1];[2:v]fps=30,fade=t=in:st=0:d=0.2,fade=t=out:st=5.75:d=0.25[v2];[3:v]fps=30,fade=t=in:st=0:d=0.2,fade=t=out:st=6.55:d=0.25[v3];[4:v]fps=30,fade=t=in:st=0:d=0.2,fade=t=out:st=6.75:d=0.25[v4];[5:v]fps=30,fade=t=in:st=0:d=0.2,fade=t=out:st=6.15:d=0.25[v5];[6:v]fps=30,fade=t=in:st=0:d=0.2,fade=t=out:st=6.55:d=0.25[v6];[7:v]fps=30,fade=t=in:st=0:d=0.2[v7];[v0][v1][v2][v3][v4][v5][v6][v7]concat=n=8:v=1:a=0,format=yuv420p[v]" \
  -map "[v]" -c:v libx264 -preset veryfast -crf 18 -movflags +faststart "$OUT"

echo "wrote $SOCIAL"
echo "wrote $SOCIAL_PNG"
echo "wrote $TRANSCRIPT"
echo "wrote $OUT"
echo "wrote $POSTER"
