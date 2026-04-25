#!/bin/zsh
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
OUT="$ROOT/assets/codex-relay-demo.mp4"
POSTER="$ROOT/assets/codex-relay-demo-poster.png"
SOCIAL="$ROOT/assets/social-card.svg"
TRANSCRIPT="$ROOT/assets/demo-transcript.svg"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

write_social() {
  cat > "$SOCIAL" <<'SVG'
<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720" role="img" aria-label="Codex Relay social card">
  <rect width="1280" height="720" fill="#080808"/>
  <rect x="56" y="56" width="1168" height="608" rx="28" fill="#111111" stroke="#2a2a2a"/>
  <text x="104" y="136" fill="#f5f5f5" font-family="Arial, sans-serif" font-size="74" font-weight="700">Codex Relay</text>
  <text x="108" y="190" fill="#b8b8b8" font-family="Arial, sans-serif" font-size="28">Telegram remote for Codex on your Mac.</text>
  <text x="108" y="238" fill="#f5f5f5" font-family="Arial, sans-serif" font-size="28">Text the bot. Your Mac does the work.</text>

  <g transform="translate(108 306)">
    <rect width="320" height="246" rx="34" fill="#050505" stroke="#303030"/>
    <rect x="24" y="26" width="272" height="42" rx="21" fill="#1f2937"/>
    <text x="44" y="54" fill="#f5f5f5" font-family="Arial, sans-serif" font-size="17" font-weight="700">Telegram</text>
    <rect x="34" y="92" width="162" height="38" rx="18" fill="#2563eb"/>
    <text x="54" y="117" fill="#ffffff" font-family="Menlo, monospace" font-size="15">/alive</text>
    <rect x="82" y="148" width="204" height="58" rx="18" fill="#171717" stroke="#333333"/>
    <text x="102" y="174" fill="#d4d4d4" font-family="Menlo, monospace" font-size="14">Mac is live</text>
    <text x="102" y="194" fill="#22c55e" font-family="Menlo, monospace" font-size="14">gpt-5.5 ready</text>
  </g>

  <text x="476" y="438" fill="#d4d4d4" font-family="Arial, sans-serif" font-size="46" font-weight="700">-></text>

  <g transform="translate(562 284)">
    <rect width="560" height="278" rx="24" fill="#050505" stroke="#303030"/>
    <rect width="560" height="44" rx="24" fill="#1a1a1a"/>
    <circle cx="30" cy="22" r="6" fill="#ef4444"/>
    <circle cx="52" cy="22" r="6" fill="#f59e0b"/>
    <circle cx="74" cy="22" r="6" fill="#22c55e"/>
    <text x="34" y="86" fill="#a7f3d0" font-family="Menlo, monospace" font-size="17">$ codex exec --model gpt-5.5</text>
    <text x="34" y="126" fill="#e5e5e5" font-family="Menlo, monospace" font-size="17">files, repos, shell</text>
    <text x="34" y="160" fill="#e5e5e5" font-family="Menlo, monospace" font-size="17">images, Computer Use, subagents</text>
    <text x="34" y="194" fill="#e5e5e5" font-family="Menlo, monospace" font-size="17">reply back to Telegram</text>
    <rect x="34" y="224" width="206" height="34" rx="17" fill="#f5f5f5"/>
    <text x="54" y="247" fill="#111111" font-family="Arial, sans-serif" font-size="15" font-weight="700">local LaunchAgent</text>
  </g>

  <text x="108" y="614" fill="#8b8b8b" font-family="Menlo, monospace" font-size="21">github.com/dicnunz/codex-relay</text>
</svg>
SVG
}

write_transcript() {
  cat > "$TRANSCRIPT" <<'SVG'
<svg xmlns="http://www.w3.org/2000/svg" width="960" height="640" viewBox="0 0 960 640" role="img" aria-label="Codex Relay Telegram transcript">
  <rect width="960" height="640" fill="#080808"/>
  <rect x="70" y="44" width="820" height="552" rx="30" fill="#111111" stroke="#2a2a2a"/>
  <text x="112" y="102" fill="#f5f5f5" font-family="Arial, sans-serif" font-size="30" font-weight="700">Codex Bridge</text>
  <text x="112" y="134" fill="#8b8b8b" font-family="Arial, sans-serif" font-size="17">Telegram -> LaunchAgent -> Codex CLI -> Mac</text>

  <g font-family="Menlo, monospace" font-size="17">
    <rect x="112" y="178" width="286" height="48" rx="20" fill="#2563eb"/>
    <text x="134" y="209" fill="#ffffff">can you see this image?</text>
    <rect x="428" y="176" width="176" height="96" rx="20" fill="#171717" stroke="#333333"/>
    <rect x="452" y="200" width="128" height="48" rx="10" fill="#262626"/>
    <text x="474" y="231" fill="#a3a3a3">screenshot</text>

    <rect x="322" y="300" width="430" height="96" rx="22" fill="#171717" stroke="#333333"/>
    <text x="348" y="332" fill="#f5f5f5">Yes. Image attached to Codex.</text>
    <text x="348" y="362" fill="#a7f3d0">Saved privately, passed with --image.</text>

    <rect x="112" y="428" width="358" height="48" rx="20" fill="#2563eb"/>
    <text x="134" y="459" fill="#ffffff">make this repo launch-ready</text>

    <rect x="322" y="504" width="454" height="58" rx="22" fill="#171717" stroke="#333333"/>
    <text x="348" y="540" fill="#f5f5f5">Done. Runtime live. Doctor passed.</text>
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
  <rect width="1280" height="720" fill="#080808"/>
  <text x="64" y="62" fill="#8b8b8b" font-family="Arial, sans-serif" font-size="18" font-weight="700">$eyebrow</text>
  <text x="64" y="126" fill="#f5f5f5" font-family="Arial, sans-serif" font-size="58" font-weight="700">$headline</text>
  <text x="68" y="172" fill="#b8b8b8" font-family="Arial, sans-serif" font-size="25">$sub</text>

  <g transform="translate(78 234)">
    <rect width="366" height="386" rx="42" fill="#050505" stroke="#303030" stroke-width="2"/>
    <rect x="24" y="28" width="318" height="48" rx="24" fill="#1f2937"/>
    <circle cx="56" cy="52" r="15" fill="#5eead4"/>
    <text x="84" y="58" fill="#f5f5f5" font-family="Arial, sans-serif" font-size="17" font-weight="700">Codex Bridge</text>
    <rect x="40" y="112" width="226" height="42" rx="20" fill="#2563eb"/>
    <text x="62" y="140" fill="#ffffff" font-family="Menlo, monospace" font-size="16">$phone_a</text>
    <rect x="92" y="184" width="228" height="72" rx="20" fill="#171717" stroke="#333333"/>
    <text x="114" y="216" fill="#f5f5f5" font-family="Menlo, monospace" font-size="16">$phone_b</text>
    <rect x="40" y="296" width="286" height="42" rx="20" fill="#2563eb"/>
    <text x="62" y="324" fill="#ffffff" font-family="Menlo, monospace" font-size="16">go do the Mac task</text>
  </g>

  <text x="504" y="448" fill="#d4d4d4" font-family="Arial, sans-serif" font-size="54" font-weight="700">-></text>

  <g transform="translate(610 224)">
    <rect width="596" height="402" rx="28" fill="#050505" stroke="#303030" stroke-width="2"/>
    <rect width="596" height="48" rx="28" fill="#1a1a1a"/>
    <circle cx="32" cy="24" r="7" fill="#ef4444"/>
    <circle cx="56" cy="24" r="7" fill="#f59e0b"/>
    <circle cx="80" cy="24" r="7" fill="#22c55e"/>
    <text x="34" y="96" fill="#a7f3d0" font-family="Menlo, monospace" font-size="19">$ mac: codex exec</text>
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

write_frame "$TMP/frame1.svg" \
  "CODEX RELAY" \
  "Text Codex from Telegram." \
  "Your Mac runs the real Codex CLI locally." \
  "/alive" \
  "Mac is live" \
  "LaunchAgent running" \
  "gpt-5.5 via Codex app CLI" \
  "no hosted relay"

write_frame "$TMP/frame2.svg" \
  "IMAGES WORK" \
  "Send a screenshot." \
  "The relay saves it privately and attaches it to Codex." \
  "what broke here?" \
  "image attached" \
  "Telegram photo downloaded" \
  "passed to Codex with --image" \
  "answer returns in chat"

write_frame "$TMP/frame3.svg" \
  "REAL MAC WORK" \
  "Ask for the actual task." \
  "Files, repos, apps, shell, Computer Use, subagents." \
  "/tools" \
  "Computer Use ok" \
  "read repo state" \
  "inspect app state" \
  "stop at human-only actions"

write_frame "$TMP/frame4.svg" \
  "INSTALL" \
  "Small repo. Local setup." \
  "BotFather token, allowlist, LaunchAgent. Nothing hosted." \
  "git clone" \
  "./scripts/install.sh" \
  "doctor passed" \
  "runtime script matches repo" \
  "github.com/dicnunz/codex-relay"

for i in 1 2 3 4; do
  render_svg "$TMP/frame$i.svg" "$TMP/frame$i.png"
done

cp "$TMP/frame2.png" "$POSTER"

ffmpeg -y -v error \
  -loop 1 -t 3.6 -i "$TMP/frame1.png" \
  -loop 1 -t 3.8 -i "$TMP/frame2.png" \
  -loop 1 -t 3.8 -i "$TMP/frame3.png" \
  -loop 1 -t 4.2 -i "$TMP/frame4.png" \
  -filter_complex "[0:v]fps=30,fade=t=out:st=3.35:d=0.25[v0];[1:v]fps=30,fade=t=in:st=0:d=0.2,fade=t=out:st=3.55:d=0.25[v1];[2:v]fps=30,fade=t=in:st=0:d=0.2,fade=t=out:st=3.55:d=0.25[v2];[3:v]fps=30,fade=t=in:st=0:d=0.2[v3];[v0][v1][v2][v3]concat=n=4:v=1:a=0,format=yuv420p[v]" \
  -map "[v]" -c:v libx264 -preset veryfast -crf 19 -movflags +faststart "$OUT"

echo "wrote $SOCIAL"
echo "wrote $TRANSCRIPT"
echo "wrote $OUT"
echo "wrote $POSTER"
