"""
api/server.py — FastAPI backend with WebSocket live updates
Endpoints: scan, history, AI analysis, report download
"""

import asyncio
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from scanner.engine import scan_host, discover_hosts, nmap_scan, nmap_available
from scanner.cve    import enrich_with_cves
from ai.analyzer    import analyze_host, analyze_network, generate_remediation_script

# ── App setup ─────────────────────────────────────────────────────────────────
app = FastAPI(title="netrecon-ai", version="1.0.0", docs_url="/docs")

app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

# ── In-memory scan store ──────────────────────────────────────────────────────
scan_store: dict[str, dict] = {}   # scan_id → scan record
ws_clients: list[WebSocket] = []   # active WebSocket connections

REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(exist_ok=True)

# ── Default port list ─────────────────────────────────────────────────────────
DEFAULT_PORTS = [
    21, 22, 23, 25, 53, 80, 110, 143, 443, 445,
    1433, 1521, 2181, 3000, 3306, 3389, 5432, 5601,
    6379, 8080, 8443, 9200, 9092, 27017,
]

# ── Pydantic models ───────────────────────────────────────────────────────────
class ScanRequest(BaseModel):
    target:   str
    ports:    Optional[list[int]] = None
    timeout:  float = 1.5
    use_nmap: bool  = False
    use_nvd:  bool  = False
    use_ai:   bool  = True

class AiRequest(BaseModel):
    scan_id: str

# ── WebSocket broadcast ───────────────────────────────────────────────────────
async def broadcast(event: str, data: dict):
    dead = []
    for ws in ws_clients:
        try:
            await ws.send_text(json.dumps({"event": event, **data}))
        except Exception:
            dead.append(ws)
    for ws in dead:
        ws_clients.remove(ws)

# ── Background scan task ──────────────────────────────────────────────────────
async def run_scan(scan_id: str, req: ScanRequest):
    record = scan_store[scan_id]
    record["status"] = "running"
    await broadcast("scan_started", {"scan_id": scan_id, "target": req.target})

    try:
        ports = req.ports or DEFAULT_PORTS
        hosts_results = []

        # Host discovery
        await broadcast("progress", {"scan_id": scan_id, "step": "discovery", "msg": f"Discovering hosts in {req.target}..."})
        live_hosts = await discover_hosts(req.target, timeout=req.timeout)

        if not live_hosts:
            # Treat target as single host if no ICMP response
            live_hosts = [req.target.split("/")[0]]

        await broadcast("progress", {"scan_id": scan_id, "step": "discovery",
                                      "msg": f"Found {len(live_hosts)} host(s)", "hosts": live_hosts})

        # Scan each host
        for i, host in enumerate(live_hosts):
            await broadcast("progress", {"scan_id": scan_id, "step": "scanning",
                                          "msg": f"Scanning {host} ({i+1}/{len(live_hosts)})...", "host": host})

            if req.use_nmap and nmap_available():
                nmap_result = nmap_scan(host)
                if "hosts" in nmap_result and nmap_result["hosts"]:
                    host_data = nmap_result["hosts"][0]
                    host_data["open_ports"] = host_data.get("ports", [])
                else:
                    host_data = await scan_host(host, ports, req.timeout)
            else:
                host_data = await scan_host(host, ports, req.timeout)

            # CVE enrichment
            await broadcast("progress", {"scan_id": scan_id, "step": "cve",
                                          "msg": f"Enriching CVEs for {host}...", "host": host})
            host_data = enrich_with_cves(host_data, use_nvd=req.use_nvd)

            # AI analysis
            ai_result = None
            if req.use_ai:
                await broadcast("progress", {"scan_id": scan_id, "step": "ai",
                                              "msg": f"Running AI analysis for {host}...", "host": host})
                ai_result = analyze_host(host_data)
                host_data["ai_analysis"] = ai_result

            hosts_results.append(host_data)
            await broadcast("host_complete", {"scan_id": scan_id, "host": host_data})

        # Network-wide AI analysis
        network_ai = None
        if req.use_ai and hosts_results:
            await broadcast("progress", {"scan_id": scan_id, "step": "network_ai",
                                          "msg": "Running network-wide AI analysis..."})
            network_ai = analyze_network(hosts_results)

        # Finalize
        record.update({
            "status":       "complete",
            "hosts":        hosts_results,
            "network_ai":   network_ai,
            "completed_at": datetime.now().isoformat(),
            "stats": {
                "hosts_scanned":  len(hosts_results),
                "total_open":     sum(h.get("open_count", 0) for h in hosts_results),
                "critical_hosts": len([h for h in hosts_results if h.get("risk_level") in ("CRITICAL","HIGH")]),
                "ports_scanned":  len(ports),
                "ai_available":   bool(os.environ.get("ANTHROPIC_API_KEY")),
            }
        })

        # Save to disk
        report_path = REPORTS_DIR / f"{scan_id}.json"
        with open(report_path, "w") as f:
            json.dump(record, f, indent=2, default=str)

        await broadcast("scan_complete", {"scan_id": scan_id, "stats": record["stats"]})

    except Exception as e:
        record["status"] = "error"
        record["error"]  = str(e)
        await broadcast("scan_error", {"scan_id": scan_id, "error": str(e)})


# ── REST Endpoints ────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    """Serve the main dashboard."""
    html_path = Path(__file__).parent.parent / "static" / "index.html"
    if html_path.exists():
        return FileResponse(str(html_path))
    return HTMLResponse("<h1>netrecon-ai · kt-it26</h1><p>Static files not found.</p>")


@app.post("/api/scan")
async def start_scan(req: ScanRequest, background_tasks: BackgroundTasks):
    """Start a new scan. Returns scan_id immediately, runs in background."""
    scan_id = str(uuid.uuid4())[:8]
    scan_store[scan_id] = {
        "scan_id":    scan_id,
        "target":     req.target,
        "status":     "queued",
        "created_at": datetime.now().isoformat(),
        "hosts":      [],
        "network_ai": None,
    }
    background_tasks.add_task(run_scan, scan_id, req)
    return {"scan_id": scan_id, "status": "queued", "target": req.target}


@app.get("/api/scan/{scan_id}")
async def get_scan(scan_id: str):
    """Get scan result by ID."""
    if scan_id not in scan_store:
        # Try loading from disk
        path = REPORTS_DIR / f"{scan_id}.json"
        if path.exists():
            with open(path) as f:
                return json.load(f)
        raise HTTPException(404, f"Scan {scan_id} not found")
    return scan_store[scan_id]


@app.get("/api/scans")
async def list_scans():
    """List all scans (in-memory + saved)."""
    scans = []
    for s in scan_store.values():
        scans.append({
            "scan_id":    s["scan_id"],
            "target":     s["target"],
            "status":     s["status"],
            "created_at": s["created_at"],
            "stats":      s.get("stats", {}),
        })
    # Also load from disk
    for path in sorted(REPORTS_DIR.glob("*.json"), reverse=True)[:20]:
        sid = path.stem
        if sid not in scan_store:
            try:
                with open(path) as f:
                    d = json.load(f)
                scans.append({
                    "scan_id":    d.get("scan_id", sid),
                    "target":     d.get("target","?"),
                    "status":     d.get("status","?"),
                    "created_at": d.get("created_at","?"),
                    "stats":      d.get("stats",{}),
                })
            except Exception:
                pass
    return {"scans": scans}


@app.post("/api/scan/{scan_id}/remediate")
async def get_remediation(scan_id: str):
    """Generate AI remediation script for a scan."""
    record = scan_store.get(scan_id)
    if not record:
        raise HTTPException(404, "Scan not found")
    hosts = record.get("hosts", [])
    if not hosts:
        raise HTTPException(400, "No host data in scan")
    # Use highest-risk host
    host = sorted(hosts, key=lambda h: h.get("risk_score", 0), reverse=True)[0]
    script = generate_remediation_script(host)
    return {"scan_id": scan_id, "host": host["ip"], "script": script}


@app.get("/api/scan/{scan_id}/report")
async def download_report(scan_id: str):
    """Download JSON report."""
    path = REPORTS_DIR / f"{scan_id}.json"
    if not path.exists():
        raise HTTPException(404, "Report not found")
    return FileResponse(str(path), filename=f"netrecon-{scan_id}.json",
                        media_type="application/json")


@app.get("/api/status")
async def status():
    return {
        "status":     "online",
        "version":    "1.0.0",
        "author":     "kt-it26",
        "nmap":       nmap_available(),
        "ai_enabled": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "scans_in_memory": len(scan_store),
    }


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    ws_clients.append(ws)
    try:
        while True:
            await ws.receive_text()  # Keep alive
    except WebSocketDisconnect:
        ws_clients.remove(ws)
