"""
scanner/engine.py — async network reconnaissance engine
Discovers hosts, fingerprints services, pulls OS info, checks CVEs
"""

import asyncio
import subprocess
import socket
import struct
import time
import json
import ipaddress
from datetime import datetime
from typing import Optional
import xml.etree.ElementTree as ET

# ── Known service metadata ────────────────────────────────────────────────────
SERVICE_META = {
    21:    {"name": "FTP",           "risk": "medium", "notes": "Unencrypted file transfer"},
    22:    {"name": "SSH",           "risk": "low",    "notes": "Secure shell — check version"},
    23:    {"name": "Telnet",        "risk": "critical","notes": "Unencrypted — should be disabled"},
    25:    {"name": "SMTP",          "risk": "medium", "notes": "Mail server"},
    53:    {"name": "DNS",           "risk": "low",    "notes": "Domain Name System"},
    80:    {"name": "HTTP",          "risk": "medium", "notes": "Unencrypted web — prefer HTTPS"},
    110:   {"name": "POP3",          "risk": "medium", "notes": "Legacy mail retrieval"},
    143:   {"name": "IMAP",          "risk": "medium", "notes": "Mail access"},
    443:   {"name": "HTTPS",         "risk": "low",    "notes": "Encrypted web"},
    445:   {"name": "SMB",           "risk": "critical","notes": "Windows file sharing — frequent attack vector"},
    1433:  {"name": "MSSQL",         "risk": "high",   "notes": "Microsoft SQL Server"},
    1521:  {"name": "Oracle DB",     "risk": "high",   "notes": "Oracle database"},
    2181:  {"name": "Zookeeper",     "risk": "high",   "notes": "Should not be internet-exposed"},
    3000:  {"name": "Node/Grafana",  "risk": "medium", "notes": "Dev server or Grafana"},
    3306:  {"name": "MySQL",         "risk": "high",   "notes": "Database — should be internal only"},
    3389:  {"name": "RDP",           "risk": "critical","notes": "Remote Desktop — brute-force target"},
    5432:  {"name": "PostgreSQL",    "risk": "high",   "notes": "Database — should be internal only"},
    5601:  {"name": "Kibana",        "risk": "high",   "notes": "Should not be internet-exposed"},
    6379:  {"name": "Redis",         "risk": "critical","notes": "Often unauthenticated — huge risk if exposed"},
    8080:  {"name": "HTTP-alt",      "risk": "medium", "notes": "Dev/proxy server"},
    8443:  {"name": "HTTPS-alt",     "risk": "low",    "notes": "Alternate HTTPS"},
    9200:  {"name": "Elasticsearch", "risk": "critical","notes": "Often unauthenticated — data exposure risk"},
    9092:  {"name": "Kafka",         "risk": "high",   "notes": "Message broker — internal only"},
    27017: {"name": "MongoDB",       "risk": "critical","notes": "Check authentication — historically exposed"},
}

RISK_SCORE = {"low": 1, "medium": 3, "high": 7, "critical": 10}

# ── Async port scanner ────────────────────────────────────────────────────────

async def scan_port(host: str, port: int, timeout: float = 1.5) -> dict:
    """Async TCP connect scan with banner grabbing."""
    start = time.time()
    result = {
        "port":      port,
        "status":    "closed",
        "latency_ms": None,
        "banner":    None,
        "service":   SERVICE_META.get(port, {}).get("name", "unknown"),
        "risk":      SERVICE_META.get(port, {}).get("risk", "unknown"),
        "notes":     SERVICE_META.get(port, {}).get("notes", ""),
    }
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
        latency = round((time.time() - start) * 1000, 2)
        result["status"]     = "open"
        result["latency_ms"] = latency

        # Try banner grab (100ms window)
        try:
            writer.write(b"HEAD / HTTP/1.0\r\n\r\n")
            await writer.drain()
            banner_bytes = await asyncio.wait_for(reader.read(256), timeout=0.8)
            banner = banner_bytes.decode("utf-8", errors="ignore").strip()
            result["banner"] = banner[:200] if banner else None
        except Exception:
            pass

        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass

    except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
        pass

    return result


async def scan_host(host: str, ports: list[int], timeout: float = 1.5) -> dict:
    """Scan all ports on a single host concurrently."""
    tasks = [scan_port(host, p, timeout) for p in ports]
    results = await asyncio.gather(*tasks)

    open_ports   = [r for r in results if r["status"] == "open"]
    risk_total   = sum(RISK_SCORE.get(r["risk"], 0) for r in open_ports)
    critical_ports = [r for r in open_ports if r["risk"] == "critical"]

    # Reverse DNS
    hostname = None
    try:
        hostname = socket.gethostbyaddr(host)[0]
    except socket.herror:
        pass

    return {
        "ip":            host,
        "hostname":      hostname,
        "scanned_at":    datetime.now().isoformat(),
        "ports":         results,
        "open_ports":    open_ports,
        "open_count":    len(open_ports),
        "risk_score":    risk_total,
        "risk_level":    _risk_level(risk_total),
        "critical_ports": critical_ports,
        "os_hint":       _guess_os(open_ports),
    }


def _risk_level(score: int) -> str:
    if score >= 20: return "CRITICAL"
    if score >= 10: return "HIGH"
    if score >= 4:  return "MEDIUM"
    if score >= 1:  return "LOW"
    return "NONE"


def _guess_os(open_ports: list) -> str:
    """Naive OS fingerprinting from open ports."""
    port_nums = {p["port"] for p in open_ports}
    if 445 in port_nums or 3389 in port_nums: return "Windows (likely)"
    if 22 in port_nums and 111 in port_nums:   return "Linux/Unix (likely)"
    if 22 in port_nums:                        return "Linux/Unix (possible)"
    if 80 in port_nums or 443 in port_nums:    return "Web server"
    return "Unknown"


# ── Network discovery ─────────────────────────────────────────────────────────

async def ping_host(host: str, timeout: float = 1.0) -> bool:
    """ICMP ping via subprocess (non-root friendly)."""
    try:
        result = await asyncio.create_subprocess_exec(
            "ping", "-c", "1", "-W", str(int(timeout * 1000)), host,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(result.wait(), timeout=timeout + 0.5)
        return result.returncode == 0
    except Exception:
        return False


async def discover_hosts(network: str, timeout: float = 1.0) -> list[str]:
    """Discover live hosts in a CIDR range."""
    try:
        net = ipaddress.ip_network(network, strict=False)
    except ValueError:
        return [network]  # single host

    # Cap at /24 for safety
    hosts = list(net.hosts())
    if len(hosts) > 254:
        hosts = hosts[:254]

    tasks  = [ping_host(str(h), timeout) for h in hosts]
    alive  = await asyncio.gather(*tasks)
    return [str(h) for h, up in zip(hosts, alive) if up]


# ── Nmap integration (optional, richer data) ─────────────────────────────────

def nmap_available() -> bool:
    try:
        subprocess.run(["nmap", "--version"], capture_output=True, timeout=5)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def nmap_scan(target: str, ports: str = "1-1024", args: str = "-sV -O --open") -> dict:
    """
    Run nmap and parse XML output.
    Returns structured dict with hosts, ports, service versions, OS.
    """
    cmd = ["nmap", "-oX", "-", "--host-timeout", "30s"] + args.split() + ["-p", ports, target]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            return {"error": result.stderr, "raw": result.stdout}
        return _parse_nmap_xml(result.stdout)
    except subprocess.TimeoutExpired:
        return {"error": "nmap scan timed out"}
    except FileNotFoundError:
        return {"error": "nmap not installed"}


def _parse_nmap_xml(xml_data: str) -> dict:
    """Parse nmap XML output into structured dict."""
    hosts = []
    try:
        root = ET.fromstring(xml_data)
        for host_el in root.findall("host"):
            status = host_el.find("status")
            if status is None or status.get("state") != "up":
                continue

            addr_el = host_el.find("address[@addrtype='ipv4']")
            ip = addr_el.get("addr") if addr_el is not None else "unknown"

            # Hostname
            hostnames = host_el.findall(".//hostname")
            hostname  = hostnames[0].get("name") if hostnames else None

            # OS
            os_matches = host_el.findall(".//osmatch")
            os_guess = os_matches[0].get("name") if os_matches else "Unknown"

            # Ports
            port_list = []
            for port_el in host_el.findall(".//port"):
                state = port_el.find("state")
                if state is None or state.get("state") != "open":
                    continue
                portid  = int(port_el.get("portid", 0))
                svc_el  = port_el.find("service")
                service = svc_el.get("name", "unknown")    if svc_el is not None else "unknown"
                product = svc_el.get("product", "")        if svc_el is not None else ""
                version = svc_el.get("version", "")        if svc_el is not None else ""
                meta    = SERVICE_META.get(portid, {})
                port_list.append({
                    "port":     portid,
                    "status":   "open",
                    "service":  service,
                    "product":  product,
                    "version":  version,
                    "risk":     meta.get("risk", "unknown"),
                    "notes":    meta.get("notes", ""),
                })

            risk_total = sum(RISK_SCORE.get(p["risk"], 0) for p in port_list)
            hosts.append({
                "ip":         ip,
                "hostname":   hostname,
                "os":         os_guess,
                "ports":      port_list,
                "open_count": len(port_list),
                "risk_score": risk_total,
                "risk_level": _risk_level(risk_total),
            })
    except ET.ParseError as e:
        return {"error": f"XML parse error: {e}"}

    return {"hosts": hosts, "total_hosts": len(hosts), "source": "nmap"}
