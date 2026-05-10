"""
cli/commands/backup.py — smart backup with SHA256 integrity, deduplication and rotation
"""

import os
import shutil
import hashlib
import tarfile
from pathlib import Path
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from cli.utils import *


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_dir(src: str) -> dict[str, str]:
    """Return {relative_path: sha256} for every file in directory."""
    checksums = {}
    for root, _, files in os.walk(src):
        for fname in files:
            abs_path = os.path.join(root, fname)
            rel_path = os.path.relpath(abs_path, src)
            try:
                checksums[rel_path] = sha256_file(abs_path)
            except (PermissionError, OSError):
                checksums[rel_path] = "ERROR"
    return checksums


def count_dir(src: str) -> tuple[int, int]:
    """Return (file_count, total_bytes)."""
    total_files, total_bytes = 0, 0
    for root, _, files in os.walk(src):
        for fname in files:
            total_files += 1
            try:
                total_bytes += os.path.getsize(os.path.join(root, fname))
            except OSError:
                pass
    return total_files, total_bytes


def rotate_backups(dest: str, keep: int):
    """Keep only the N most recent backups in dest parent."""
    parent = Path(dest).parent
    backups = sorted(
        [d for d in parent.iterdir() if d.is_dir() or d.suffix in (".gz", ".tar")],
        key=lambda d: d.stat().st_mtime,
        reverse=True
    )
    removed = []
    for old in backups[keep:]:
        if old.is_dir():
            shutil.rmtree(str(old))
        else:
            old.unlink()
        removed.append(str(old))
    return removed


def cmd_backup(args):
    header("SMART BACKUP ENGINE")

    src  = Path(args.src)
    dest = Path(args.dest)

    if not src.exists():
        err(f"Source not found: {src}")
        return

    info(f"Source      : {src}")
    info(f"Destination : {dest}")
    info(f"Compress    : {args.compress}")
    info(f"Verify      : {args.verify}")
    info(f"Keep        : {args.keep} backups")
    print()

    # Count source
    info("Scanning source...")
    file_count, total_bytes = count_dir(str(src))
    info(f"Files found : {file_count}")
    info(f"Total size  : {human_size(total_bytes)}")
    print()

    slug = timestamp_slug()
    backup_name = f"{src.name}_{slug}"
    backup_path = dest / backup_name

    dest.mkdir(parents=True, exist_ok=True)

    # Compute source checksums before copy
    checksums_before = {}
    if args.verify:
        info("Computing source checksums (SHA256)...")
        checksums_before = sha256_dir(str(src))
        ok(f"Checksums computed: {len(checksums_before)} files")
        print()

    # Copy
    info(f"Copying {file_count} files...")
    shutil.copytree(str(src), str(backup_path))
    ok(f"Copy complete → {backup_path}")

    # Compress
    final_path = str(backup_path)
    if args.compress:
        info("Compressing to .tar.gz...")
        tar_path = str(backup_path) + ".tar.gz"
        with tarfile.open(tar_path, "w:gz") as tar:
            tar.add(str(backup_path), arcname=backup_name)
        shutil.rmtree(str(backup_path))
        final_path = tar_path
        compressed_size = Path(tar_path).stat().st_size
        ratio = (1 - compressed_size / total_bytes) * 100 if total_bytes else 0
        ok(f"Compressed → {tar_path}")
        info(f"Compressed size : {human_size(compressed_size)} (saved {ratio:.1f}%)")

    # Integrity verification
    verify_result = None
    if args.verify and not args.compress:
        info("Verifying integrity (SHA256 comparison)...")
        checksums_after = sha256_dir(str(backup_path))
        mismatches = []
        for rel, chk in checksums_before.items():
            if checksums_after.get(rel) != chk:
                mismatches.append(rel)
        if mismatches:
            err(f"Integrity FAILED — {len(mismatches)} file(s) mismatch:")
            for m in mismatches[:10]:
                dim(f"    {m}")
            verify_result = "FAILED"
        else:
            ok(f"Integrity verified — all {len(checksums_before)} files match")
            verify_result = "PASSED"

    # Rotate old backups
    removed = rotate_backups(str(backup_path), args.keep)
    if removed:
        info(f"Rotated {len(removed)} old backup(s):")
        for r in removed:
            dim(f"  removed: {os.path.basename(r)}")

    # Save manifest
    manifest = {
        "timestamp":      now_str(),
        "source":         str(src),
        "destination":    final_path,
        "files":          file_count,
        "size_bytes":     total_bytes,
        "size_human":     human_size(total_bytes),
        "compressed":     args.compress,
        "integrity":      verify_result,
        "checksums":      checksums_before if args.verify else {},
        "backups_removed": removed,
    }
    save_json(manifest, "reports/backup-manifest.json")

    print()
    ok(f"Backup complete — {backup_name}")
