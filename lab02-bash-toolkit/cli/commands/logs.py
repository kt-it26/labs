"""
cli/commands/logs.py — smart log rotation with compression and audit trail
"""

import os
import gzip
import shutil
import glob
from pathlib import Path
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from cli.utils import *


def get_log_files(directory: str) -> list[dict]:
    """Scan directory for log files recursively."""
    files = []
    for pattern in ["*.log", "*.log.*", "syslog", "auth.log", "kern.log"]:
        for path in Path(directory).rglob(pattern):
            try:
                stat = path.stat()
                files.append({
                    "path": str(path),
                    "name": path.name,
                    "size_bytes": stat.st_size,
                    "size_human": human_size(stat.st_size),
                    "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                })
            except PermissionError:
                pass
    return sorted(files, key=lambda x: x["size_bytes"], reverse=True)


def rotate_file(file_path: str, dest_dir: str, compress: bool, dry_run: bool) -> dict:
    """Rotate a single log file."""
    src = Path(file_path)
    slug = timestamp_slug()
    rotated_name = f"{src.stem}.{slug}.log"
    dest = Path(dest_dir) / rotated_name

    result = {
        "source": str(src),
        "destination": str(dest),
        "compressed": False,
        "size_before": src.stat().st_size,
        "action": "dry-run" if dry_run else "rotated",
    }

    if dry_run:
        return result

    Path(dest_dir).mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(src), str(dest))

    if compress:
        gz_path = str(dest) + ".gz"
        with open(str(dest), "rb") as f_in, gzip.open(gz_path, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        dest.unlink()
        result["destination"] = gz_path
        result["compressed"] = True
        result["size_after"] = Path(gz_path).stat().st_size

    # Truncate original (standard rotation behavior)
    open(str(src), "w").close()
    result["size_after"] = result.get("size_after", 0)
    return result


def cleanup_old_rotations(dest_dir: str, base_name: str, keep: int):
    """Remove old rotated files beyond keep limit."""
    pattern = str(Path(dest_dir) / f"{Path(base_name).stem}.*")
    files = sorted(glob.glob(pattern), reverse=True)
    removed = []
    for f in files[keep:]:
        os.remove(f)
        removed.append(f)
    return removed


def cmd_logs(args):
    header("LOG ROTATION ENGINE")
    info(f"Scanning: {args.dir}")
    info(f"Max size: {args.max_size} MB  |  Keep: {args.keep}  |  Compress: {args.compress}  |  Dry-run: {args.dry_run}")
    print()

    files = get_log_files(args.dir)
    if not files:
        warn(f"No log files found in {args.dir}")
        return

    max_bytes = args.max_size * 1024 * 1024
    needs_rotation = [f for f in files if f["size_bytes"] >= max_bytes]
    small_files    = [f for f in files if f["size_bytes"] < max_bytes]

    # Show summary table
    table(files[:20], ["name", "size_human", "modified"])

    info(f"Total files found : {len(files)}")
    info(f"Need rotation     : {len(needs_rotation)} (>= {args.max_size}MB)")
    info(f"OK (under limit)  : {len(small_files)}")
    print()

    if not needs_rotation:
        ok("All log files are within size limits. Nothing to rotate.")
        return

    archive_dir = str(Path(args.dir) / "rotated")
    results = []

    for f in needs_rotation:
        info(f"Rotating: {f['name']} ({f['size_human']})")
        result = rotate_file(f["path"], archive_dir, args.compress, args.dry_run)
        results.append(result)

        removed = []
        if not args.dry_run:
            removed = cleanup_old_rotations(archive_dir, f["path"], args.keep)

        action = "would rotate" if args.dry_run else "rotated"
        suffix = " [gzipped]" if result["compressed"] else ""
        ok(f"{action}: {f['name']}{suffix}")
        if removed:
            for r in removed:
                dim(f"    removed old: {os.path.basename(r)}")

    print()
    summary = {
        "timestamp": now_str(),
        "directory": args.dir,
        "files_rotated": len(results),
        "dry_run": args.dry_run,
        "results": results,
    }
    save_json(summary, "reports/log-rotation.json")
    ok(f"Rotation complete. {len(results)} file(s) processed.")
