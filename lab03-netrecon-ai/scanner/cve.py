"""
scanner/cve.py — CVE lookup and vulnerability enrichment
Uses NVD (National Vulnerability Database) public API — no key needed
"""

import urllib.request
import urllib.parse
import json
import time
from datetime import datetime

NVD_API = "https://services.nvd.nist.gov/rest/json/cves/2.0"

# ── Local CVE knowledge base (offline fallback — no internet needed) ──────────
# Curated high-impact CVEs for common services seen in DevOps environments
OFFLINE_CVE_DB = {
    "redis": [
        {"id": "CVE-2022-0543", "score": 10.0, "severity": "CRITICAL",
         "description": "Lua sandbox escape in Redis allows RCE via eval command",
         "published": "2022-03-04"},
        {"id": "CVE-2023-28425", "score": 5.5, "severity": "MEDIUM",
         "description": "Specially crafted SRANDMEMBER, ZRANDMEMBER, HRANDFIELD commands cause OOM"},
    ],
    "openssh": [
        {"id": "CVE-2023-38408", "score": 9.8, "severity": "CRITICAL",
         "description": "Remote code execution in ssh-agent via forwarded agent socket"},
        {"id": "CVE-2024-6387", "score": 8.1, "severity": "HIGH",
         "description": "regreSSHion: race condition in signal handler allows unauthenticated RCE"},
    ],
    "nginx": [
        {"id": "CVE-2021-23017", "score": 7.7, "severity": "HIGH",
         "description": "Off-by-one in DNS resolver allows heap write and potential RCE"},
    ],
    "apache": [
        {"id": "CVE-2021-41773", "score": 7.5, "severity": "HIGH",
         "description": "Path traversal and RCE in Apache HTTP Server 2.4.49"},
        {"id": "CVE-2021-42013", "score": 9.8, "severity": "CRITICAL",
         "description": "Incomplete fix for CVE-2021-41773 allows RCE without mod_cgi"},
    ],
    "mysql": [
        {"id": "CVE-2023-21912", "score": 7.5, "severity": "HIGH",
         "description": "Unauthenticated remote DoS via crafted packet in MySQL Server"},
    ],
    "postgresql": [
        {"id": "CVE-2023-2454", "score": 7.2, "severity": "HIGH",
         "description": "Row security policy bypass via schema manipulation"},
    ],
    "mongodb": [
        {"id": "CVE-2021-32040", "score": 7.5, "severity": "HIGH",
         "description": "DoS via crafted aggregation pipeline expressions"},
    ],
    "elasticsearch": [
        {"id": "CVE-2021-22145", "score": 6.5, "severity": "MEDIUM",
         "description": "Memory disclosure via crafted query to _async_search endpoint"},
    ],
    "smb": [
        {"id": "CVE-2020-0796", "score": 10.0, "severity": "CRITICAL",
         "description": "SMBGhost: Buffer overflow in SMBv3 allows wormable RCE without auth"},
        {"id": "CVE-2017-0144",  "score": 9.3,  "severity": "CRITICAL",
         "description": "EternalBlue: SMBv1 allows unauthenticated RCE — used in WannaCry"},
    ],
    "rdp": [
        {"id": "CVE-2019-0708", "score": 9.8, "severity": "CRITICAL",
         "description": "BlueKeep: Pre-auth RCE in RDP — wormable, no user interaction"},
        {"id": "CVE-2021-34535", "score": 8.8, "severity": "HIGH",
         "description": "Remote Desktop Client RCE when connecting to malicious server"},
    ],
    "telnet": [
        {"id": "CVE-2020-10188", "score": 9.8, "severity": "CRITICAL",
         "description": "Buffer overflow in telnetd allows unauthenticated RCE"},
    ],
    "ftp": [
        {"id": "CVE-2010-4221", "score": 10.0, "severity": "CRITICAL",
         "description": "Stack overflow in ProFTPD allows pre-auth unauthenticated RCE"},
    ],
}

# Port → service key mapping for offline DB lookup
PORT_TO_SERVICE = {
    21: "ftp", 22: "openssh", 23: "telnet", 25: "smtp",
    80: "apache", 443: "nginx",
    445: "smb", 3306: "mysql", 3389: "rdp",
    5432: "postgresql", 6379: "redis",
    8080: "apache", 9200: "elasticsearch", 27017: "mongodb",
}


def get_cves_offline(port: int, service_name: str = "") -> list[dict]:
    """Return CVEs from local knowledge base for a given port/service."""
    # Try by port mapping first
    key = PORT_TO_SERVICE.get(port)
    if key and key in OFFLINE_CVE_DB:
        return OFFLINE_CVE_DB[key]
    # Try by service name substring
    svc = service_name.lower()
    for k, cves in OFFLINE_CVE_DB.items():
        if k in svc or svc in k:
            return cves
    return []


def get_cves_nvd(keyword: str, max_results: int = 3) -> list[dict]:
    """
    Query NVD API for CVEs matching a keyword.
    Free, no API key required. Rate limited to ~5 req/30s.
    """
    params = urllib.parse.urlencode({
        "keywordSearch": keyword,
        "resultsPerPage": max_results,
    })
    url = f"{NVD_API}?{params}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "netrecon-ai/1.0 kt-it26"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())

        cves = []
        for item in data.get("vulnerabilities", []):
            cve = item.get("cve", {})
            cve_id = cve.get("id", "")
            desc_list = cve.get("descriptions", [])
            desc = next((d["value"] for d in desc_list if d["lang"] == "en"), "")
            metrics = cve.get("metrics", {})

            # Try CVSS v3.1 first, then v3.0, then v2
            score, severity = None, "UNKNOWN"
            for ver in ["cvssMetricV31", "cvssMetricV30", "cvssMetricV2"]:
                m = metrics.get(ver, [])
                if m:
                    cvss_data = m[0].get("cvssData", {})
                    score     = cvss_data.get("baseScore")
                    severity  = cvss_data.get("baseSeverity", "UNKNOWN")
                    break

            cves.append({
                "id":          cve_id,
                "score":       score,
                "severity":    severity,
                "description": desc[:300],
                "published":   cve.get("published", "")[:10],
                "source":      "NVD API",
            })
        return cves

    except Exception:
        return []  # Silently fall back to offline DB


def enrich_with_cves(scan_result: dict, use_nvd: bool = False) -> dict:
    """
    Add CVE data to each open port in a scan result.
    use_nvd=True makes live API calls (slower, requires internet).
    """
    for port_data in scan_result.get("open_ports", []):
        port    = port_data.get("port", 0)
        service = port_data.get("service", "")
        product = port_data.get("product", "")

        cves = []

        if use_nvd and (product or service):
            keyword = product or service
            cves = get_cves_nvd(keyword, max_results=3)
            time.sleep(0.2)  # Respect NVD rate limit

        if not cves:
            cves = get_cves_offline(port, service)

        port_data["cves"]          = cves
        port_data["cve_count"]     = len(cves)
        port_data["max_cve_score"] = max((c.get("score") or 0 for c in cves), default=0)
        port_data["has_critical"]  = any(c.get("severity") == "CRITICAL" for c in cves)

    return scan_result
