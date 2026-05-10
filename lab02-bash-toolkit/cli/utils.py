"""
cli/utils.py — shared helpers for all commands
"""

import os
import sys
import json
import time
from datetime import datetime
from pathlib import Path

# ── Colors ────────────────────────────────────────────────────────────────────
C = {
    "green":  "\033[92m",
    "yellow": "\033[93m",
    "red":    "\033[91m",
    "cyan":   "\033[96m",
    "silver": "\033[37m",
    "dim":    "\033[90m",
    "bold":   "\033[1m",
    "reset":  "\033[0m",
}

def ok(msg):    print(f"  {C['green']}✓{C['reset']}  {msg}")
def warn(msg):  print(f"  {C['yellow']}⚠{C['reset']}  {msg}")
def err(msg):   print(f"  {C['red']}✗{C['reset']}  {msg}")
def info(msg):  print(f"  {C['cyan']}·{C['reset']}  {msg}")
def dim(msg):   print(f"  {C['dim']}{msg}{C['reset']}")

def header(title: str):
    print(f"\n{C['bold']}{C['silver']}  {'─'*50}{C['reset']}")
    print(f"{C['bold']}  {title}{C['reset']}")
    print(f"{C['bold']}{C['silver']}  {'─'*50}{C['reset']}\n")

def table(rows: list[dict], columns: list[str]):
    """Print a minimal ASCII table."""
    if not rows:
        dim("  (no data)")
        return
    widths = {col: len(col) for col in columns}
    for row in rows:
        for col in columns:
            widths[col] = max(widths[col], len(str(row.get(col, ""))))
    header_line = "  " + "  ".join(col.upper().ljust(widths[col]) for col in columns)
    print(f"{C['dim']}{header_line}{C['reset']}")
    print(f"{C['dim']}  {'  '.join('─'*widths[col] for col in columns)}{C['reset']}")
    for row in rows:
        line = "  " + "  ".join(str(row.get(col, "")).ljust(widths[col]) for col in columns)
        print(line)
    print()

def save_json(data: dict | list, path: str):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    ok(f"Saved → {path}")

def load_json(path: str) -> dict | list | None:
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

def human_size(bytes_: int) -> str:
    for unit in ["B","KB","MB","GB","TB"]:
        if bytes_ < 1024:
            return f"{bytes_:.1f} {unit}"
        bytes_ /= 1024
    return f"{bytes_:.1f} PB"

def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def timestamp_slug() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")
