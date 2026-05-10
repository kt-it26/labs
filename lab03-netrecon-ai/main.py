#!/usr/bin/env python3
"""
netrecon-ai · kt-it26 · lab03
Network reconnaissance platform with AI analysis

Usage:
  python3 main.py                     # start web server
  python3 main.py --scan 192.168.1.1  # CLI scan
  python3 main.py --scan 192.168.1.0/24 --ports 22,80,443
"""

import argparse
import asyncio
import json
import os
import sys
import uvicorn
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

BANNER = """
\033[1;32m
  ███╗   ██╗███████╗████████╗██████╗ ███████╗ ██████╗ ██████╗ ███╗   ██╗
  ████╗  ██║██╔════╝╚══██╔══╝██╔══██╗██╔════╝██╔════╝██╔═══██╗████╗  ██║
  ██╔██╗ ██║█████╗     ██║   ██████╔╝█████╗  ██║     ██║   ██║██╔██╗ ██║
  ██║╚██╗██║██╔══╝     ██║   ██╔══██╗██╔══╝  ██║     ██║   ██║██║╚██╗██║
  ██║ ╚████║███████╗   ██║   ██║  ██║███████╗╚██████╗╚██████╔╝██║ ╚████║
  ╚═╝  ╚═══╝╚══════╝   ╚═╝   ╚═╝  ╚═╝╚══════╝ ╚═════╝ ╚═════╝ ╚═╝  ╚═══╝
\033[0m\033[1;32m  ·AI·\033[0m\033[90m  network reconnaissance platform · kt-it26 · lab03\033[0m
"""


async def cli_scan(target: str, ports: list[int], use_ai: bool, use_nvd: bool):
    from scanner.engine import scan_host, discover_hosts
    from scanner.cve    import enrich_with_cves
    from ai.analyzer    import analyze_host, analyze_network

    C = {
        "g": "\033[92m", "y": "\033[93m", "r": "\033[91m",
        "c": "\033[96m", "d": "\033[90m", "b": "\033[1m", "x": "\033[0m"
    }

    print(BANNER)
    print(f"  {C['c']}Target{C['x']} : {target}")
    print(f"  {C['c']}Ports {C['x']} : {len(ports)} ports")
    print(f"  {C['c']}AI    {C['x']} : {'enabled' if use_ai else 'disabled'}")
    print(f"  {C['c']}NVD   {C['x']} : {'live lookup' if use_nvd else 'offline DB'}")
    print()

    # Discover
    print(f"  {C['d']}[1/4] Discovering hosts...{C['x']}")
    live = await discover_hosts(target)
    if not live:
        live = [target.split("/")[0]]
    print(f"  {C['g']}✓{C['x']}  {len(live)} host(s) found: {', '.join(live[:5])}")

    hosts_data = []
    for i, host in enumerate(live, 1):
        print(f"\n  {C['d']}[2/4] Scanning {host} ({i}/{len(live)})...{C['x']}")
        data = await scan_host(host, ports)
        open_p = data.get("open_ports", [])
        print(f"  {C['g']}✓{C['x']}  {len(open_p)} open ports | risk: {data.get('risk_level','?')} (score {data.get('risk_score',0)})")

        if open_p:
            print(f"\n  {'PORT':<8} {'SERVICE':<20} {'RISK':<10} {'LATENCY'}")
            print(f"  {'─'*8} {'─'*20} {'─'*10} {'─'*10}")
            for p in open_p:
                risk = p.get("risk","?")
                color = C['r'] if risk=="critical" else C['y'] if risk=="high" else C['g']
                lat = f"{p.get('latency_ms',0):.1f}ms" if p.get('latency_ms') else "—"
                print(f"  {p['port']:<8} {p.get('service','?'):<20} {color}{risk:<10}{C['x']} {lat}")

        print(f"\n  {C['d']}[3/4] Enriching CVEs...{C['x']}")
        data = enrich_with_cves(data, use_nvd=use_nvd)
        total_cves = sum(p.get("cve_count", 0) for p in open_p)
        print(f"  {C['g']}✓{C['x']}  {total_cves} CVEs mapped")

        if use_ai:
            print(f"  {C['d']}[4/4] Running AI analysis...{C['x']}")
            ai = analyze_host(data)
            data["ai_analysis"] = ai
            ai_src = "Claude AI" if ai.get("ai_available") else "rule-based"
            print(f"  {C['g']}✓{C['x']}  Analysis complete ({ai_src})")
            print(f"\n  {C['b']}Summary:{C['x']} {ai.get('summary','')}")
            if ai.get("anomalies"):
                print(f"  {C['b']}Anomalies:{C['x']}")
                for a in ai["anomalies"][:3]:
                    print(f"    {C['y']}⚠{C['x']}  {a}")
            if ai.get("recommendations"):
                print(f"  {C['b']}Recommendations:{C['x']}")
                for r in ai["recommendations"][:3]:
                    print(f"    {C['g']}→{C['x']}  {r}")

        hosts_data.append(data)

    # Save
    Path("reports").mkdir(exist_ok=True)
    from datetime import datetime
    slug    = datetime.now().strftime("%Y%m%d_%H%M%S")
    outfile = f"reports/scan_{slug}.json"
    with open(outfile, "w") as f:
        json.dump({"target": target, "hosts": hosts_data,
                   "generated_at": slug}, f, indent=2, default=str)
    print(f"\n  {C['g']}✓{C['x']}  Report saved → {outfile}")
    print(f"  {C['d']}  Start the web UI for the full dashboard: python3 main.py{C['x']}\n")


def main():
    parser = argparse.ArgumentParser(
        prog="netrecon-ai",
        description="kt-it26 · Network Reconnaissance Platform with AI"
    )
    parser.add_argument("--scan",     help="Target IP, hostname or CIDR (e.g. 192.168.1.0/24)")
    parser.add_argument("--ports",    help="Comma-separated ports (default: top 24 DevOps ports)")
    parser.add_argument("--no-ai",    action="store_true", help="Disable AI analysis")
    parser.add_argument("--nvd",      action="store_true", help="Live CVE lookup from NVD API")
    parser.add_argument("--host",     default="0.0.0.0",  help="Web server host")
    parser.add_argument("--port",     type=int, default=8000, help="Web server port")
    args = parser.parse_args()

    print(BANNER)

    if args.scan:
        from scanner.engine import DEFAULT_PORTS
        ports = [int(p) for p in args.ports.split(",")] if args.ports else DEFAULT_PORTS
        asyncio.run(cli_scan(args.scan, ports, not args.no_ai, args.nvd))
    else:
        ai_status = "✓ AI enabled" if os.environ.get("ANTHROPIC_API_KEY") else "⚠ No API key — rule-based analysis only"
        print(f"  \033[96mStarting web server\033[0m")
        print(f"  Dashboard  : http://localhost:{args.port}")
        print(f"  API docs   : http://localhost:{args.port}/docs")
        print(f"  AI status  : {ai_status}")
        print(f"  Set AI key : export ANTHROPIC_API_KEY=sk-ant-...\n")
        uvicorn.run("api.server:app", host=args.host, port=args.port,
                    reload=False, log_level="warning")


if __name__ == "__main__":
    main()
