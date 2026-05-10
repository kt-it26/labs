#!/usr/bin/env bash
# scripts/backup.sh
# Smart backup with timestamp, compression and checksum
# Usage: bash backup.sh <source> <destination> [compress=yes|no]

set -euo pipefail

SRC="${1:?Usage: backup.sh <source> <dest> [yes|no]}"
DEST="${2:?Usage: backup.sh <source> <dest> [yes|no]}"
COMPRESS="${3:-yes}"

SLUG=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="$(basename "$SRC")_${SLUG}"
BACKUP_PATH="$DEST/$BACKUP_NAME"

GREEN='\033[92m'; YELLOW='\033[93m'; RESET='\033[0m'; BOLD='\033[1m'
ok()   { echo -e "  ${GREEN}✓${RESET}  $1"; }
info() { echo -e "  ·  $1"; }

echo -e "\n${BOLD}  BACKUP SCRIPT · kt-it26${RESET}"
echo -e "  ─────────────────────────\n"
info "Source      : $SRC"
info "Destination : $DEST"
info "Compress    : $COMPRESS"
echo ""

[[ -d "$SRC" ]] || { echo "Source not found: $SRC"; exit 1; }
mkdir -p "$DEST"

# Count files
FILE_COUNT=$(find "$SRC" -type f | wc -l)
TOTAL_SIZE=$(du -sh "$SRC" 2>/dev/null | cut -f1)
info "Files: $FILE_COUNT  |  Size: $TOTAL_SIZE"
echo ""

# Checksum before
info "Computing checksums..."
CHECKSUM_FILE="/tmp/backup_checksums_${SLUG}.sha256"
find "$SRC" -type f -exec sha256sum {} \; > "$CHECKSUM_FILE" 2>/dev/null
ok "Checksums computed: $(wc -l < "$CHECKSUM_FILE") files"

# Copy
info "Copying..."
cp -a "$SRC" "$BACKUP_PATH"
ok "Copied → $BACKUP_PATH"

# Compress
if [[ "$COMPRESS" == "yes" ]]; then
    info "Compressing..."
    tar -czf "${BACKUP_PATH}.tar.gz" -C "$DEST" "$BACKUP_NAME"
    rm -rf "$BACKUP_PATH"
    FINAL="${BACKUP_PATH}.tar.gz"
    FINAL_SIZE=$(du -sh "$FINAL" | cut -f1)
    ok "Compressed → $FINAL ($FINAL_SIZE)"
else
    FINAL="$BACKUP_PATH"
fi

# Save checksum file alongside backup
cp "$CHECKSUM_FILE" "$DEST/${BACKUP_NAME}.sha256"
ok "Checksums saved → $DEST/${BACKUP_NAME}.sha256"

echo ""
ok "Backup complete: $BACKUP_NAME"
echo ""
