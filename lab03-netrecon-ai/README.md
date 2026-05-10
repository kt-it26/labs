# lab03-netrecon-ai

Network reconnaissance platform with AI-powered analysis. Discovers hosts, fingerprints services, maps CVEs, and uses Claude AI to generate threat assessments and remediation scripts — all in real time via a WebSocket-powered dashboard.

**Lab 03** of my DevOps portfolio · kt-it26

---

## Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI + asyncio |
| Live updates | WebSockets |
| Scanner | Async TCP + optional nmap |
| CVE data | NVD API + offline knowledge base |
| AI analysis | Claude Sonnet (Anthropic API) |
| Frontend | Vanilla JS + WebSocket client |

---

## Quick start

```bash
git clone https://github.com/kt-it26/lab03-netrecon-ai
cd lab03-netrecon-ai
pip3 install -r requirements.txt

# Optional: enable AI analysis
export ANTHROPIC_API_KEY=sk-ant-...

# Start web server
python3 main.py
# Open http://localhost:8000
```

### CLI mode (no browser needed)

```bash
# Scan a single host
python3 main.py --scan 192.168.1.1

# Scan a full subnet
python3 main.py --scan 192.168.1.0/24

# Specific ports + live CVE lookup
python3 main.py --scan 10.0.0.1 --ports 22,80,443,3306,6379 --nvd
```

---

## Features

**Network scanning**
- Async TCP connect scan — scans 24 ports concurrently per host
- Banner grabbing — captures service banners for fingerprinting
- Host discovery — ICMP ping sweep across CIDR ranges
- Reverse DNS lookup for every discovered host
- Naive OS fingerprinting from open port combinations
- Optional nmap integration for richer service/version data

**CVE enrichment**
- Offline knowledge base — 30+ curated CVEs for common DevOps services
- Live NVD API lookup — optional, queries nvd.nist.gov in real time
- Risk scoring — per-port and per-host risk scores with CRITICAL/HIGH/MEDIUM/LOW levels

**AI analysis (Claude Sonnet)**
- Per-host threat assessment — anomaly detection, attack vectors, recommendations
- Network-wide analysis — executive summary, patterns, priority actions
- Remediation script generator — produces runnable bash scripts for detected issues
- Graceful degradation — rule-based fallback when no API key is set

**Dashboard**
- WebSocket live updates — results stream in as each host completes
- Terminal log panel — real-time scan output
- Interactive host cards — expandable with port tables and CVE pills
- Remediation modal — generate and view bash scripts in one click

---

## Project structure

```
lab03-netrecon-ai/
├── main.py                  # Entry point — web server or CLI
├── scanner/
│   ├── engine.py            # Async TCP scanner, host discovery, nmap integration
│   └── cve.py               # CVE enrichment — offline DB + NVD API
├── ai/
│   └── analyzer.py          # Claude AI analysis + rule-based fallback
├── api/
│   └── server.py            # FastAPI + WebSocket server
├── static/
│   └── index.html           # Full dashboard (single-file, no build needed)
├── reports/                 # JSON scan reports (git-ignored)
├── requirements.txt
└── README.md
```

---

## Environment variables

```bash
ANTHROPIC_API_KEY=sk-ant-...   # Enable Claude AI analysis
HOST=0.0.0.0                   # Server bind address (default: 0.0.0.0)
PORT=8000                      # Server port (default: 8000)
```

---

## API reference

```
POST /api/scan              Start a new scan
GET  /api/scan/{id}         Get scan result
GET  /api/scans             List all scans
POST /api/scan/{id}/remediate  Generate remediation script
GET  /api/scan/{id}/report  Download JSON report
GET  /api/status            Service status
WS   /ws                    WebSocket for live events
GET  /docs                  FastAPI auto-generated docs
```

---

## Skills demonstrated

| Skill | Where |
|---|---|
| Async Python | `engine.py` — asyncio, concurrent port scanning |
| FastAPI + WebSockets | `server.py` — background tasks, WS broadcast |
| API integration | `analyzer.py` — Anthropic Claude API |
| CVE/security data | `cve.py` — NVD API + offline knowledge base |
| Network programming | `engine.py` — raw TCP, ICMP, banner grabbing |
| Frontend real-time | `index.html` — WebSocket client, live DOM updates |

---

## Part of my DevOps portfolio

→ [lab01-sysmon-agent](https://github.com/kt-it26/lab01-sysmon-agent)
→ [lab02-bash-toolkit](https://github.com/kt-it26/lab02-bash-toolkit)
→ [View all 15 labs](https://github.com/kt-it26)
