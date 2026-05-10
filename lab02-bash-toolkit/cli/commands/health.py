"""
cli/commands/health.py — port/service health scanner with latency tracking and history
"""

import socket
import time
import json
import subprocess
from pathlib import Path
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from cli.utils import *

# Known service names by port
KNOWN_SERVICES = {
    21: "FTP", 22: "SSH", 25: "SMTP", 53: "DNS",
    80: "HTTP", 443: "HTTPS", 3306: "MySQL",
    5432: "PostgreSQL", 6379: "Redis", 8080: "HTTP-alt",
    8443: "HTTPS-alt", 9200: "Elasticsearch", 27017: "MongoDB",
    2181: "Zookeeper", 9092: "Kafka", 5672: "RabbitMQ",
}


def check_port(host: str, port: int, timeout: float) -> dict:
    start = time.time()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            latency_ms = (time.time() - start) * 1000
            return {
                "port":       port,
                "service":    KNOWN_SERVICES.get(port, "unknown"),
                "status":     "open",
                "latency_ms": round(latency_ms, 2),
                "timestamp":  now_str(),
            }
    except (socket.timeout, ConnectionRefusedError, OSError) as e:
        return {
            "port":       port,
            "service":    KNOWN_SERVICES.get(port, "unknown"),
            "status":     "closed",
            "latency_ms": None,
            "error":      str(e),
            "timestamp":  now_str(),
        }


def check_systemd_service(name: str) -> dict:
    """Check if a systemd service is active."""
    try:
        result = subprocess.run(
            ["systemctl", "is-active", name],
            capture_output=True, text=True, timeout=5
        )
        status = result.stdout.strip()
        return {"service": name, "status": status, "active": status == "active"}
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return {"service": name, "status": "unknown", "active": False}


def load_history(output_path: str) -> list:
    data = load_json(output_path)
    if isinstance(data, list):
        return data
    return []


def print_results(results: list[dict], host: str):
    print(f"\n  {'PORT':<8} {'SERVICE':<16} {'STATUS':<10} {'LATENCY':>10}")
    print(f"  {'─'*8} {'─'*16} {'─'*10} {'─'*10}")
    for r in results:
        if r["status"] == "open":
            status_str = f"{C['green']}● open{C['reset']}"
            latency    = f"{r['latency_ms']:.1f} ms"
        else:
            status_str = f"{C['red']}○ closed{C['reset']}"
            latency    = "  —"
        svc = r.get("service", "unknown")
        print(f"  {r['port']:<8} {svc:<16} {status_str:<18} {latency:>10}")
    print()


def cmd_health(args):
    header("PORT & SERVICE HEALTH SCANNER")

    ports   = [int(p.strip()) for p in args.ports.split(",")]
    host    = args.host
    timeout = args.timeout

    info(f"Host    : {host}")
    info(f"Ports   : {args.ports}")
    info(f"Timeout : {timeout}s")

    history = load_history(args.output)
    run_num = 0

    while True:
        run_num += 1
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"\n{C['dim']}  [{ts}] scan #{run_num}{C['reset']}")

        results = []
        for port in ports:
            r = check_port(host, port, timeout)
            results.append(r)

        print_results(results, host)

        open_ports   = [r for r in results if r["status"] == "open"]
        closed_ports = [r for r in results if r["status"] == "closed"]

        ok(f"Open   : {len(open_ports)}/{len(results)}")
        if closed_ports:
            warn(f"Closed : {len(closed_ports)} — {', '.join(str(r['port']) for r in closed_ports)}")

        if open_ports:
            avg_lat = sum(r["latency_ms"] for r in open_ports) / len(open_ports)
            info(f"Avg latency : {avg_lat:.1f} ms")

        # Track history
        scan_record = {
            "scan_id":   run_num,
            "timestamp": now_str(),
            "host":      host,
            "results":   results,
            "summary": {
                "open":   len(open_ports),
                "closed": len(closed_ports),
                "total":  len(results),
            }
        }
        history.append(scan_record)
        # Keep last 500 scans
        if len(history) > 500:
            history = history[-500:]

        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as f:
            json.dump(history, f, indent=2)

        if args.interval <= 0:
            break

        print(f"\n{C['dim']}  Next scan in {args.interval}s... (Ctrl+C to stop){C['reset']}")
        try:
            time.sleep(args.interval)
        except KeyboardInterrupt:
            print(f"\n{C['dim']}  Stopped.{C['reset']}\n")
            break

    ok(f"Health log saved → {args.output}")
    info(f"Total scans recorded: {len(history)}")
