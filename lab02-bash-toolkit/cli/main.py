#!/usr/bin/env python3
"""
lab02-bash-toolkit · kt-it26
Unified DevOps CLI — log rotation, backup, port health, inventory, service watchdog.
"""

import argparse
import sys
import os

# Add parent dir to path so scripts can import shared utils
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cli.commands.logs     import cmd_logs
from cli.commands.backup   import cmd_backup
from cli.commands.health   import cmd_health
from cli.commands.inventory import cmd_inventory
from cli.commands.watchdog import cmd_watchdog
from cli.commands.report   import cmd_report

BANNER = """
\033[1;32m  ██████╗ ███████╗██╗   ██╗ ██████╗ ██████╗ ███████╗
  ██╔══██╗██╔════╝██║   ██║██╔═══██╗██╔══██╗██╔════╝
  ██║  ██║█████╗  ██║   ██║██║   ██║██████╔╝███████╗
  ██║  ██║██╔══╝  ╚██╗ ██╔╝██║   ██║██╔═══╝ ╚════██║
  ██████╔╝███████╗ ╚████╔╝ ╚██████╔╝██║     ███████║
  ╚═════╝ ╚══════╝  ╚═══╝   ╚═════╝ ╚═╝     ╚══════╝\033[0m
\033[90m  bash-toolkit · kt-it26 · lab02\033[0m
"""

def main():
    print(BANNER)

    parser = argparse.ArgumentParser(
        prog="devops",
        description="kt-it26 · DevOps Bash Toolkit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
commands:
  logs        Rotate, compress and archive log files
  backup      Backup directories with deduplication and integrity check
  health      Port/service health scanner with history
  inventory   Full system inventory (packages, services, hardware)
  watchdog    Monitor and auto-restart services
  report      Generate HTML report from all collected data

examples:
  devops logs --dir /var/log --max-size 50 --keep 7
  devops backup --src /home/user --dest /backup --compress
  devops health --ports 22,80,443,3306,5432 --interval 30
  devops inventory --output reports/inventory.json
  devops watchdog --services nginx,postgresql,redis --restart
  devops report --output reports/devops-report.html
        """
    )

    sub = parser.add_subparsers(dest="command")

    # ── logs ──────────────────────────────────────────────────────────────────
    p_logs = sub.add_parser("logs", help="Rotate and archive log files")
    p_logs.add_argument("--dir",      default="/var/log", help="Directory to scan")
    p_logs.add_argument("--max-size", type=int, default=50, help="Max file size in MB before rotation")
    p_logs.add_argument("--keep",     type=int, default=7,  help="Number of rotated files to keep")
    p_logs.add_argument("--compress", action="store_true",  help="Gzip rotated files")
    p_logs.add_argument("--dry-run",  action="store_true",  help="Show what would happen, no changes")

    # ── backup ────────────────────────────────────────────────────────────────
    p_back = sub.add_parser("backup", help="Smart directory backup")
    p_back.add_argument("--src",      required=True, help="Source directory")
    p_back.add_argument("--dest",     required=True, help="Destination directory")
    p_back.add_argument("--compress", action="store_true", help="Create .tar.gz archive")
    p_back.add_argument("--verify",   action="store_true", help="SHA256 integrity check")
    p_back.add_argument("--keep",     type=int, default=5,  help="Max backups to keep")

    # ── health ────────────────────────────────────────────────────────────────
    p_health = sub.add_parser("health", help="Port and service health check")
    p_health.add_argument("--ports",    default="22,80,443", help="Comma-separated ports")
    p_health.add_argument("--host",     default="localhost",  help="Host to check")
    p_health.add_argument("--interval", type=int, default=0, help="Repeat interval in seconds (0=once)")
    p_health.add_argument("--timeout",  type=float, default=2.0, help="Connection timeout")
    p_health.add_argument("--output",   default="reports/health.json", help="Save results to JSON")

    # ── inventory ─────────────────────────────────────────────────────────────
    p_inv = sub.add_parser("inventory", help="System inventory snapshot")
    p_inv.add_argument("--output", default="reports/inventory.json", help="Output JSON file")
    p_inv.add_argument("--full",   action="store_true", help="Include all installed packages")

    # ── watchdog ──────────────────────────────────────────────────────────────
    p_dog = sub.add_parser("watchdog", help="Service watchdog with auto-restart")
    p_dog.add_argument("--services", required=True, help="Comma-separated service names")
    p_dog.add_argument("--interval", type=int, default=10, help="Check interval in seconds")
    p_dog.add_argument("--restart",  action="store_true",  help="Auto-restart failed services")
    p_dog.add_argument("--log",      default="reports/watchdog.log", help="Log file")

    # ── report ────────────────────────────────────────────────────────────────
    p_rep = sub.add_parser("report", help="Generate HTML report")
    p_rep.add_argument("--output", default="reports/devops-report.html", help="Output HTML file")
    p_rep.add_argument("--open",   action="store_true", help="Open in browser after generating")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    dispatch = {
        "logs":      cmd_logs,
        "backup":    cmd_backup,
        "health":    cmd_health,
        "inventory": cmd_inventory,
        "watchdog":  cmd_watchdog,
        "report":    cmd_report,
    }

    dispatch[args.command](args)


if __name__ == "__main__":
    main()
