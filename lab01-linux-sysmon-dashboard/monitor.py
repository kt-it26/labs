#!/usr/bin/env python3
"""
linux-sysmon-dashboard
Real-time Linux system monitor with alerting and JSON/CSV export.
"""

import argparse
import json
import csv
import logging
import time
import os
import signal
import sys
from datetime import datetime
from pathlib import Path

import psutil
import yaml

# ── Logging setup ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stderr),
        logging.FileHandler("logs/sysmon.log"),
    ],
)
log = logging.getLogger("sysmon")


# ── Config loader ─────────────────────────────────────────────────────────────
def load_config(path: str = "config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


# ── Metric collectors ─────────────────────────────────────────────────────────
def collect_cpu(interval: float = 1.0) -> dict:
    percent = psutil.cpu_percent(interval=interval)
    freq = psutil.cpu_freq()
    return {
        "percent": percent,
        "count_logical": psutil.cpu_count(logical=True),
        "count_physical": psutil.cpu_count(logical=False),
        "freq_mhz": round(freq.current, 1) if freq else None,
    }


def collect_memory() -> dict:
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    return {
        "total_gb": round(mem.total / 1e9, 2),
        "used_gb": round(mem.used / 1e9, 2),
        "available_gb": round(mem.available / 1e9, 2),
        "percent": mem.percent,
        "swap_total_gb": round(swap.total / 1e9, 2),
        "swap_used_gb": round(swap.used / 1e9, 2),
        "swap_percent": swap.percent,
    }


def collect_disk(paths: list) -> list:
    results = []
    for path in paths:
        try:
            usage = psutil.disk_usage(path)
            results.append({
                "path": path,
                "total_gb": round(usage.total / 1e9, 2),
                "used_gb": round(usage.used / 1e9, 2),
                "free_gb": round(usage.free / 1e9, 2),
                "percent": usage.percent,
            })
        except PermissionError:
            log.warning(f"Cannot access disk path: {path}")
    return results


def collect_network() -> dict:
    net = psutil.net_io_counters()
    return {
        "bytes_sent_mb": round(net.bytes_sent / 1e6, 2),
        "bytes_recv_mb": round(net.bytes_recv / 1e6, 2),
        "packets_sent": net.packets_sent,
        "packets_recv": net.packets_recv,
        "errin": net.errin,
        "errout": net.errout,
    }


def collect_processes(top_n: int = 5) -> list:
    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "status"]):
        try:
            procs.append(p.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return sorted(procs, key=lambda x: x.get("cpu_percent") or 0, reverse=True)[:top_n]


def snapshot(config: dict) -> dict:
    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "hostname": os.uname().nodename,
        "cpu": collect_cpu(config.get("cpu_interval", 1.0)),
        "memory": collect_memory(),
        "disk": collect_disk(config.get("disk_paths", ["/"])),
        "network": collect_network(),
        "top_processes": collect_processes(config.get("top_processes", 5)),
    }


# ── Alert engine ──────────────────────────────────────────────────────────────
class AlertEngine:
    def __init__(self, thresholds: dict):
        self.thresholds = thresholds
        self._triggered: set = set()

    def check(self, data: dict) -> list[dict]:
        alerts = []
        t = self.thresholds

        def _alert(key, metric, value, limit, unit=""):
            msg = f"ALERT [{key.upper()}] {metric} at {value}{unit} — threshold {limit}{unit}"
            if key not in self._triggered:
                log.warning(msg)
                self._triggered.add(key)
            alerts.append({"key": key, "metric": metric, "value": value, "threshold": limit})

        def _clear(key):
            if key in self._triggered:
                log.info(f"CLEAR [{key.upper()}] back to normal")
                self._triggered.discard(key)

        # CPU
        cpu_pct = data["cpu"]["percent"]
        if cpu_pct >= t.get("cpu_percent", 90):
            _alert("cpu", "CPU usage", cpu_pct, t["cpu_percent"], "%")
        else:
            _clear("cpu")

        # Memory
        mem_pct = data["memory"]["percent"]
        if mem_pct >= t.get("memory_percent", 85):
            _alert("memory", "Memory usage", mem_pct, t["memory_percent"], "%")
        else:
            _clear("memory")

        # Swap
        swap_pct = data["memory"]["swap_percent"]
        if swap_pct >= t.get("swap_percent", 50):
            _alert("swap", "Swap usage", swap_pct, t["swap_percent"], "%")
        else:
            _clear("swap")

        # Disk
        for disk in data["disk"]:
            key = f"disk_{disk['path']}"
            if disk["percent"] >= t.get("disk_percent", 80):
                _alert(key, f"Disk {disk['path']}", disk["percent"], t["disk_percent"], "%")
            else:
                _clear(key)

        return alerts


# ── Exporters ─────────────────────────────────────────────────────────────────
class JsonExporter:
    def __init__(self, output_dir: str, max_entries: int = 1000):
        self.path = Path(output_dir) / "metrics.json"
        self.max_entries = max_entries
        self.entries: list = []

        if self.path.exists():
            with open(self.path) as f:
                self.entries = json.load(f)

    def write(self, data: dict):
        self.entries.append(data)
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries:]
        with open(self.path, "w") as f:
            json.dump(self.entries, f, indent=2)


class CsvExporter:
    def __init__(self, output_dir: str):
        self.path = Path(output_dir) / "metrics.csv"
        self._write_header = not self.path.exists()

    def write(self, data: dict):
        row = {
            "timestamp": data["timestamp"],
            "hostname": data["hostname"],
            "cpu_percent": data["cpu"]["percent"],
            "memory_percent": data["memory"]["percent"],
            "swap_percent": data["memory"]["swap_percent"],
            "disk_root_percent": next(
                (d["percent"] for d in data["disk"] if d["path"] == "/"), None
            ),
            "net_sent_mb": data["network"]["bytes_sent_mb"],
            "net_recv_mb": data["network"]["bytes_recv_mb"],
        }
        with open(self.path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=row.keys())
            if self._write_header:
                writer.writeheader()
                self._write_header = False
            writer.writerow(row)


# ── Display ───────────────────────────────────────────────────────────────────
COLORS = {
    "red": "\033[91m", "yellow": "\033[93m",
    "green": "\033[92m", "cyan": "\033[96m",
    "bold": "\033[1m", "reset": "\033[0m",
}


def bar(percent: float, width: int = 20) -> str:
    filled = int(width * percent / 100)
    color = COLORS["green"]
    if percent >= 80:
        color = COLORS["red"]
    elif percent >= 60:
        color = COLORS["yellow"]
    return f"{color}{'█' * filled}{'░' * (width - filled)}{COLORS['reset']} {percent:5.1f}%"


def render(data: dict, alerts: list):
    os.system("clear")
    c = COLORS
    print(f"{c['bold']}{c['cyan']}╔══════════════════════════════════════════════╗{c['reset']}")
    print(f"{c['bold']}{c['cyan']}║       linux-sysmon-dashboard  v1.0           ║{c['reset']}")
    print(f"{c['bold']}{c['cyan']}╚══════════════════════════════════════════════╝{c['reset']}")
    print(f"  Host : {data['hostname']}    Time : {data['timestamp']}")
    print()

    cpu = data["cpu"]
    print(f"{c['bold']}  CPU{c['reset']}  {cpu['count_physical']}p/{cpu['count_logical']}t  {cpu['freq_mhz']} MHz")
    print(f"  Usage  {bar(cpu['percent'])}")
    print()

    mem = data["memory"]
    print(f"{c['bold']}  MEMORY{c['reset']}  {mem['used_gb']} / {mem['total_gb']} GB")
    print(f"  RAM    {bar(mem['percent'])}")
    print(f"  Swap   {bar(mem['swap_percent'])}")
    print()

    print(f"{c['bold']}  DISK{c['reset']}")
    for d in data["disk"]:
        print(f"  {d['path']:<12} {bar(d['percent'])}  {d['free_gb']} GB free")
    print()

    net = data["network"]
    print(f"{c['bold']}  NETWORK{c['reset']}")
    print(f"  Sent : {net['bytes_sent_mb']:>10.2f} MB    Recv : {net['bytes_recv_mb']:>10.2f} MB")
    print(f"  Errors in/out : {net['errin']} / {net['errout']}")
    print()

    print(f"{c['bold']}  TOP PROCESSES{c['reset']}")
    print(f"  {'PID':<8} {'NAME':<22} {'CPU%':>6} {'MEM%':>6}")
    print(f"  {'─'*8} {'─'*22} {'─'*6} {'─'*6}")
    for p in data["top_processes"]:
        print(f"  {p['pid']:<8} {(p['name'] or '?')[:22]:<22} "
              f"{(p['cpu_percent'] or 0):>6.1f} {(p['memory_percent'] or 0):>6.1f}")
    print()

    if alerts:
        print(f"{c['red']}{c['bold']}  ⚠ ALERTS ({len(alerts)}){c['reset']}")
        for a in alerts:
            print(f"  {c['red']}▶ {a['metric']} : {a['value']} (threshold: {a['threshold']}){c['reset']}")
    else:
        print(f"{c['green']}  ✓ All metrics within normal thresholds{c['reset']}")
    print()
    print(f"  Output → reports/metrics.json  |  reports/metrics.csv")
    print(f"  Press Ctrl+C to stop\n")


# ── Main loop ─────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Linux System Monitor")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument("--interval", type=int, help="Override poll interval (seconds)")
    parser.add_argument("--no-display", action="store_true", help="Run headless (for systemd)")
    parser.add_argument("--once", action="store_true", help="Collect one snapshot and exit")
    args = parser.parse_args()

    config = load_config(args.config)
    if args.interval:
        config["interval"] = args.interval

    Path("logs").mkdir(exist_ok=True)
    Path("reports").mkdir(exist_ok=True)

    alert_engine = AlertEngine(config.get("thresholds", {}))
    json_exp = JsonExporter("reports", config.get("max_json_entries", 1000))
    csv_exp = CsvExporter("reports")

    log.info(f"sysmon started | interval={config['interval']}s | host={os.uname().nodename}")

    def _shutdown(sig, frame):
        log.info("sysmon stopped")
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    while True:
        data = snapshot(config)
        alerts = alert_engine.check(data)
        json_exp.write(data)
        csv_exp.write(data)

        if not args.no_display:
            render(data, alerts)

        if args.once:
            print(json.dumps(data, indent=2))
            break

        time.sleep(config.get("interval", 5))


if __name__ == "__main__":
    main()
