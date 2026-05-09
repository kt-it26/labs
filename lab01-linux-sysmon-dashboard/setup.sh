#!/usr/bin/env bash
# setup.sh — install linux-sysmon-dashboard as a systemd service
# Run as root: sudo bash setup.sh

set -euo pipefail

INSTALL_DIR="/opt/linux-sysmon-dashboard"
SERVICE_FILE="/etc/systemd/system/sysmon.service"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

print_step() { echo -e "\n\033[1;36m[STEP]\033[0m $1"; }
print_ok()   { echo -e "\033[1;32m  ✓ $1\033[0m"; }
print_err()  { echo -e "\033[1;31m  ✗ $1\033[0m"; exit 1; }

# ── Checks ────────────────────────────────────────────────────────────────────
[[ $EUID -ne 0 ]] && print_err "Please run as root: sudo bash setup.sh"

print_step "Checking dependencies..."
command -v python3 >/dev/null 2>&1 || print_err "python3 not found. Install it first."
command -v pip3    >/dev/null 2>&1 || print_err "pip3 not found. Install python3-pip first."
print_ok "Dependencies OK"

# ── Install Python packages ───────────────────────────────────────────────────
print_step "Installing Python requirements..."
pip3 install -r "$REPO_DIR/requirements.txt" -q
print_ok "Python packages installed"

# ── Copy files ────────────────────────────────────────────────────────────────
print_step "Copying files to $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR/logs" "$INSTALL_DIR/reports"
cp "$REPO_DIR/monitor.py" "$INSTALL_DIR/"
cp "$REPO_DIR/config.yaml" "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/monitor.py"
print_ok "Files copied"

# ── Install service ───────────────────────────────────────────────────────────
print_step "Installing systemd service..."
sed "s|/opt/linux-sysmon-dashboard|$INSTALL_DIR|g" \
    "$REPO_DIR/sysmon.service" > "$SERVICE_FILE"
systemctl daemon-reload
systemctl enable sysmon.service
systemctl start  sysmon.service
print_ok "Service installed and started"

# ── Status ────────────────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  sysmon installed successfully!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Status  : systemctl status sysmon"
echo "  Logs    : journalctl -u sysmon -f"
echo "  Metrics : $INSTALL_DIR/reports/metrics.json"
echo "  CSV     : $INSTALL_DIR/reports/metrics.csv"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

systemctl status sysmon --no-pager
