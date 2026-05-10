#!/usr/bin/env bash
# scripts/log-rotate.sh
# Native bash log rotation — alternative to the Python CLI
# Usage: sudo bash log-rotate.sh [LOG_DIR] [MAX_SIZE_MB] [KEEP]
# Example: sudo bash log-rotate.sh /var/log 50 7

set -euo pipefail

LOG_DIR="${1:-/var/log}"
MAX_SIZE_MB="${2:-50}"
KEEP="${3:-7}"
ARCHIVE_DIR="$LOG_DIR/rotated"
REPORT_FILE="/tmp/log-rotate-report-$(date +%Y%m%d_%H%M%S).txt"

GREEN='\033[92m'; YELLOW='\033[93m'; RED='\033[91m'; RESET='\033[0m'; BOLD='\033[1m'

log()  { echo -e "  ${GREEN}✓${RESET}  $1" | tee -a "$REPORT_FILE"; }
warn() { echo -e "  ${YELLOW}⚠${RESET}  $1" | tee -a "$REPORT_FILE"; }
info() { echo -e "  ·  $1"                  | tee -a "$REPORT_FILE"; }

echo -e "\n${BOLD}  LOG ROTATION SCRIPT · kt-it26${RESET}"
echo -e "  ────────────────────────────────\n"
info "Directory  : $LOG_DIR"
info "Max size   : ${MAX_SIZE_MB}MB"
info "Keep       : $KEEP rotated copies"
echo ""

mkdir -p "$ARCHIVE_DIR"

ROTATED=0
MAX_BYTES=$(( MAX_SIZE_MB * 1024 * 1024 ))

while IFS= read -r -d '' file; do
    size=$(stat -c%s "$file" 2>/dev/null || echo 0)

    if (( size >= MAX_BYTES )); then
        name=$(basename "$file")
        slug=$(date +%Y%m%d_%H%M%S)
        dest="$ARCHIVE_DIR/${name%.log}.${slug}.log"

        cp "$file" "$dest"
        gzip -f "$dest"
        truncate -s 0 "$file"

        size_human=$(numfmt --to=iec "$size" 2>/dev/null || echo "${size}B")
        log "Rotated: $name ($size_human) → $(basename "$dest").gz"
        (( ROTATED++ )) || true

        # Cleanup old rotations
        mapfile -t old_files < <(ls -t "$ARCHIVE_DIR/${name%.log}".*.log.gz 2>/dev/null || true)
        for (( i=KEEP; i<${#old_files[@]}; i++ )); do
            rm -f "${old_files[$i]}"
            warn "Removed old: $(basename "${old_files[$i]}")"
        done
    fi
done < <(find "$LOG_DIR" -maxdepth 2 -name "*.log" -print0 2>/dev/null)

echo ""
log "Done. $ROTATED file(s) rotated."
info "Report saved: $REPORT_FILE"
echo ""
