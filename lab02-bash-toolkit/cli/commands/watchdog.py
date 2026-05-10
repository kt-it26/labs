"""
cli/commands/watchdog.py — service watchdog with auto-restart and incident log
"""

import subprocess
import time
import signal
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from cli.utils import *


def service_status(name: str) -> dict:
    try:
        result = subprocess.run(
            ["systemctl", "is-active", name],
            capture_output=True, text=True, timeout=5
        )
        status = result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        status = "unknown"

    # Get more detail
    detail = ""
    try:
        r2 = subprocess.run(
            ["systemctl", "show", name, "--property=MainPID,ActiveState,SubState"],
            capture_output=True, text=True, timeout=5
        )
        detail = r2.stdout.strip()
    except Exception:
        pass

    props = {}
    for line in detail.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            props[k] = v

    return {
        "name":         name,
        "active":       status == "active",
        "status":       status,
        "active_state": props.get("ActiveState", "?"),
        "sub_state":    props.get("SubState", "?"),
        "main_pid":     props.get("MainPID", "?"),
        "timestamp":    now_str(),
    }


def restart_service(name: str) -> bool:
    try:
        result = subprocess.run(
            ["systemctl", "restart", name],
            capture_output=True, text=True, timeout=30
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
        return False


def log_event(log_path: str, event: dict):
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    line = f"[{event['timestamp']}] {event['service']} | {event['event']} | {event.get('detail','')}\n"
    with open(log_path, "a") as f:
        f.write(line)


def print_status_table(statuses: list[dict]):
    print(f"\n  {'SERVICE':<24} {'STATE':<12} {'SUB':<12} {'PID':<8} {'STATUS'}")
    print(f"  {'─'*24} {'─'*12} {'─'*12} {'─'*8} {'─'*8}")
    for s in statuses:
        if s["active"]:
            indicator = f"{C['green']}●{C['reset']}"
            state_str = f"{C['green']}{s['active_state']}{C['reset']}"
        else:
            indicator = f"{C['red']}○{C['reset']}"
            state_str = f"{C['red']}{s['active_state']}{C['reset']}"
        print(f"  {indicator} {s['name']:<22} {state_str:<20} {s['sub_state']:<12} {s['main_pid']:<8}")
    print()


def cmd_watchdog(args):
    header("SERVICE WATCHDOG")

    services  = [s.strip() for s in args.services.split(",")]
    interval  = args.interval
    do_restart = args.restart
    log_path  = args.log

    info(f"Watching : {', '.join(services)}")
    info(f"Interval : {interval}s")
    info(f"Restart  : {'YES — will auto-restart failed services' if do_restart else 'NO — monitor only'}")
    info(f"Log      : {log_path}")
    print()

    incidents     = 0
    restarts_done = 0
    check_count   = 0

    def _shutdown(sig, frame):
        print(f"\n{C['dim']}  Watchdog stopped. Checks: {check_count} | Incidents: {incidents} | Restarts: {restarts_done}{C['reset']}\n")
        sys.exit(0)

    signal.signal(signal.SIGINT,  _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    while True:
        check_count += 1
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"{C['dim']}  [{ts}] check #{check_count}{C['reset']}", end="\r")

        statuses = [service_status(name) for name in services]
        failed   = [s for s in statuses if not s["active"]]
        healthy  = [s for s in statuses if s["active"]]

        if failed or check_count % 10 == 1:  # Full print on first/every 10 or on failure
            print_status_table(statuses)

        for s in failed:
            incidents += 1
            event = {
                "timestamp": now_str(),
                "service":   s["name"],
                "event":     "DOWN",
                "detail":    f"state={s['status']}"
            }
            log_event(log_path, event)
            err(f"Service DOWN: {s['name']} (state={s['status']})")

            if do_restart:
                info(f"Attempting restart: {s['name']}...")
                success = restart_service(s["name"])
                if success:
                    restarts_done += 1
                    ok(f"Restarted: {s['name']}")
                    log_event(log_path, {
                        "timestamp": now_str(), "service": s["name"],
                        "event": "RESTARTED", "detail": "auto-restart OK"
                    })
                else:
                    err(f"Restart FAILED: {s['name']} (needs sudo?)")
                    log_event(log_path, {
                        "timestamp": now_str(), "service": s["name"],
                        "event": "RESTART_FAILED", "detail": "insufficient privileges or service error"
                    })

        if healthy and not failed:
            pass  # silent when all good

        time.sleep(interval)
