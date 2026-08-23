#!/usr/bin/env bash
# ==============================================================================
# Setup Polkit & Sudoers Rules for Netools DNS Management
# Allows applying DNS via resolvectl & nmcli without repeated password prompts.
# ==============================================================================

set -euo pipefail

CURRENT_USER="${SUDO_USER:-$(whoami)}"

if [ "$EUID" -ne 0 ]; then
    echo "⚠️  This script requires administrative privileges."
    echo "Please run: sudo bash $0"
    exit 1
fi

echo "⚡ Setting up passwordless Polkit rules for Netools (User: $CURRENT_USER)..."

# 1. Polkit Rule
POLKIT_DIR="/etc/polkit-1/rules.d"
if [ -d "$POLKIT_DIR" ]; then
    cat << 'EOF' > "$POLKIT_DIR/50-netools-dns.rules"
// Allow Netools to manage DNS via systemd-resolved and NetworkManager without password prompt
polkit.addRule(function(action, subject) {
    if (
        action.id == "org.freedesktop.resolve1.set-dns-servers" ||
        action.id == "org.freedesktop.resolve1.set-domains" ||
        action.id == "org.freedesktop.resolve1.set-default-route" ||
        action.id == "org.freedesktop.resolve1.set-dnsovertls" ||
        action.id == "org.freedesktop.resolve1.revert" ||
        action.id == "org.freedesktop.NetworkManager.network-control" ||
        action.id == "org.freedesktop.NetworkManager.settings.modify.system"
    ) {
        return polkit.Result.YES;
    }
});
EOF
    chmod 644 "$POLKIT_DIR/50-netools-dns.rules"
    echo "✓ Installed: $POLKIT_DIR/50-netools-dns.rules"
fi

# 2. Sudoers Rule fallback
SUDOERS_DIR="/etc/sudoers.d"
if [ -d "$SUDOERS_DIR" ]; then
    cat << EOF > "$SUDOERS_DIR/netools-dns"
# Allow $CURRENT_USER to run resolvectl and nmcli without password
$CURRENT_USER ALL=(ALL) NOPASSWD: /usr/bin/resolvectl, /usr/bin/nmcli
EOF
    chmod 440 "$SUDOERS_DIR/netools-dns"
    echo "✓ Installed: $SUDOERS_DIR/netools-dns"
fi

echo ""
echo "🎉 Done! Netools can now switch DNS and toggle DoT with 0 password prompts."
