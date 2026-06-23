#!/bin/zsh
# Bygger (eller bygger om) skrivbordsappen "Dalecarlia Cull.app" med rätt ikon.
# Kör efter en ominstallation om skrivbordsikonen tappats. Idempotent.
#
#   ./scripts/skrivbordsapp.sh
#
set -e

ASSETS="$(cd "$(dirname "$0")/../src/cull/assets" && pwd)"
PNG="$ASSETS/icon.png"
APP="$HOME/Desktop/Dalecarlia Cull.app"
BIN="$HOME/.local/bin"
PY="$HOME/.local/pipx/venvs/cull/bin/python"

# 1) Launcher: laddar API-nyckeln ur ~/.zshrc, sätter PATH, startar webb-GUI:t.
mkdir -p "$BIN"
cat > "$BIN/cull-start" <<'EOF'
#!/bin/zsh
cd "$HOME" 2>/dev/null || true
[ -f "$HOME/.zshrc" ] && eval "$(grep '^export ANTHROPIC_API_KEY=' "$HOME/.zshrc" | tail -1)"
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"
exec "$HOME/.local/bin/cull-web"
EOF
chmod +x "$BIN/cull-start"

# 2) AppleScript-applet: startar launchern utan terminalfönster.
rm -rf "$APP"
osacompile -o "$APP" -e \
  'do shell script "nohup \"$HOME/.local/bin/cull-start\" >/dev/null 2>&1 &"'

# 3) Ikon: regenerera applet.icns ur loggan (bundle-självständig) ...
SET="$(mktemp -d)/icon.iconset"; mkdir -p "$SET"
for s in 16 32 128 256 512; do
  sips -z $s $s "$PNG" --out "$SET/icon_${s}x${s}.png" >/dev/null 2>&1
  d=$((s*2)); sips -z $d $d "$PNG" --out "$SET/icon_${s}x${s}@2x.png" >/dev/null 2>&1
done
iconutil -c icns "$SET" -o "$APP/Contents/Resources/applet.icns"

# ... och sätt custom-ikon via Cocoa så Finder visar loggan direkt.
"$PY" - "$PNG" "$APP" <<'PY'
import sys
from AppKit import NSWorkspace, NSImage
img = NSImage.alloc().initWithContentsOfFile_(sys.argv[1])
NSWorkspace.sharedWorkspace().setIcon_forFile_options_(img, sys.argv[2], 0)
PY
touch "$APP"

echo "Klart: $APP (logga satt, startar cull-web)"
