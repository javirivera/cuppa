#!/usr/bin/env bash
#
# Installer for `cuppa` — works two ways:
#   • From a clone:   ./install.sh            (copies the local cuppa.py)
#   • One-liner:      curl -fsSL https://raw.githubusercontent.com/javirivera/cuppa/main/install.sh | bash
#     (the one-liner only works once the repo is public)
#
set -euo pipefail

RAW_BASE="https://raw.githubusercontent.com/javirivera/cuppa/main"

# Pick an install dir on PATH that we can write to.
if [ -w "/usr/local/bin" ]; then
  BIN="/usr/local/bin"
else
  BIN="$HOME/.local/bin"
  mkdir -p "$BIN"
fi
DEST="$BIN/cuppa"

# Source the script: prefer a local copy (clone), else download it.
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-/dev/null}")" 2>/dev/null && pwd || true)"
if [ -n "$SELF_DIR" ] && [ -f "$SELF_DIR/cuppa.py" ]; then
  cp "$SELF_DIR/cuppa.py" "$DEST"
else
  echo "Downloading cuppa from $RAW_BASE/cuppa.py ..."
  curl -fsSL "$RAW_BASE/cuppa.py" -o "$DEST"
fi
chmod +x "$DEST"

echo "✓ Installed cuppa to $DEST"

# Warn if python3 is missing (macOS doesn't ship it by default).
if ! command -v python3 >/dev/null 2>&1; then
  echo "⚠  python3 not found. Install Xcode Command Line Tools (xcode-select --install)"
  echo "   or Homebrew Python (brew install python) to run cuppa."
fi

# If the chosen bin dir isn't on PATH, persist it to the user's shell profile
# instead of just warning (a warning is easy to miss/skip, and the install
# would otherwise need to be repeated every time a new shell is opened).
case ":$PATH:" in
  *":$BIN:"*) : ;;
  *)
    case "${SHELL:-}" in
      */zsh) PROFILE="$HOME/.zshrc" ;;
      */bash) PROFILE="$HOME/.bash_profile" ;;
      *) PROFILE="$HOME/.profile" ;;
    esac
    LINE="export PATH=\"$BIN:\$PATH\" # Added by cuppa installer"
    touch "$PROFILE"
    if ! grep -qxF "$LINE" "$PROFILE"; then
      printf '\n%s\n' "$LINE" >> "$PROFILE"
      echo "✓ Added $BIN to PATH in $PROFILE"
    fi
    echo "  Restart your terminal (or run: source $PROFILE) for this to take effect."
    ;;
esac

echo "Run it with:  cuppa"
