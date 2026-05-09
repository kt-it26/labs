# linux-sysmon-dashboard

Real-time Linux system monitor with configurable alerting and automatic export to JSON and CSV. Runs as an interactive terminal dashboard or as a headless `systemd` service in the background.

Built as **Lab 01** of my DevOps portfolio — demonstrating Python systems scripting, Linux service management, and observability fundamentals.

---

## What it does

- Collects CPU, memory, swap, disk and network metrics every N seconds (configurable)
- Renders a live color-coded terminal dashboard with usage bars
- Fires alerts when any metric crosses a configured threshold (with auto-clear when it recovers)
- Exports all data to `reports/metrics.json` and `reports/metrics.csv` continuously
- Runs as a `systemd` service with auto-restart on failure
- Fires alerts when any metric crosses a configured threshold (with auto-clear when it recovers). You can customize alerts, for example set CPU or RAM thresholds so that if they exceed, for example, 60%, an alert is generated
- Runs locally in real-time at http://127.0.0.1:5000/

---

## Demo

```
╔══════════════════════════════════════════════╗
║       linux-sysmon-dashboard  v1.0           ║
╚══════════════════════════════════════════════╝
  By kt-it26

  Host : myserver    Time : 2026-05-09T14:32:01Z

  CPU  4p/8t  3600.0 MHz
  Usage  ████████░░░░░░░░░░░░  41.2%

  MEMORY  5.83 / 15.93 GB
  RAM    ████████████░░░░░░░░  61.4%
  Swap   ░░░░░░░░░░░░░░░░░░░░   0.0%

  DISK
  /            ██████████░░░░░░░░░░  48.3%  102.4 GB free

  NETWORK
  Sent :      1432.55 MB    Recv :      8721.03 MB

  TOP PROCESSES
  PID      NAME                   CPU%   MEM%
  ──────── ────────────────────── ────── ──────
  1842     chrome                  12.3    4.1
  991      python3                  8.7    1.2
  ...

  ✓ All metrics within normal thresholds

  Output → reports/metrics.json  |  reports/metrics.csv
  Press Ctrl+C to stop
```

---

## Architecture

```
┌─────────────────────────────────────────────┐
│              monitor.py                     │
│                                             │
│  Collectors          AlertEngine            │
│  ├── collect_cpu()   ├── threshold check    │
│  ├── collect_mem()   ├── triggered set      │
│  ├── collect_disk()  └── clear on recover   │
│  ├── collect_net()                          │
│  └── collect_procs()  Exporters             │
│                       ├── JsonExporter      │
│  render() ──────────► └── CsvExporter       │
│  (terminal UI)                              │
└─────────────────────────────────────────────┘
         │
         ▼ when deployed as service
┌─────────────────────┐
│   systemd / sysmon  │
│   --no-display mode │
│   auto-restart      │
└─────────────────────┘
```

---

## Project structure

```
linux-sysmon-dashboard/
├── web.py              # Local Web
├── monitor.py          # Main agent — collectors, alerts, exporters, UI
├── config.yaml         # Thresholds, paths, intervals (edit this)
├── sysmon.service      # systemd unit file
├── setup.sh            # One-command install as systemd service
├── requirements.txt
├── .gitignore
├── logs/               # Runtime logs (git-ignored)
└── reports/            # JSON + CSV output (git-ignored)
```

---

## Quick start

### 1. Clone and install dependencies

```bash
git clone https://github.com/kt-it26/linux-sysmon-dashboard
cd linux-sysmon-dashboard
pip3 install -r requirements.txt
```

### 2. Run the live dashboard

```bash
python3 monitor.py for terminal or web.py run local http://127.0.0.1:5000
```

### 3. Run once and print JSON (useful for testing)

```bash
python3 monitor.py --once
```

### 4. Override poll interval

```bash
python3 monitor.py --interval 2
```

### 5. Run headless (no terminal UI, just export + alerts to stdout)

```bash
python3 monitor.py --no-display
```

---

## Install as systemd service

Runs in the background, survives reboots, auto-restarts on crash.

```bash
sudo bash setup.sh
```

Then:

```bash
# Check status
systemctl status sysmon

# Follow logs
journalctl -u sysmon -f

# Stop / disable
systemctl stop sysmon
systemctl disable sysmon
```

---

## Configuration

Edit `config.yaml`:

```yaml
interval: 5              # seconds between polls

disk_paths:
  - /
  - /home                # add any mount point

top_processes: 5

thresholds:
  cpu_percent: 85        # alert when CPU > 85%
  memory_percent: 80
  swap_percent: 50
  disk_percent: 80
```

---

## Output files

**`reports/metrics.json`** — rolling array of snapshots (max 1000 entries):

```json
[
  {
    "timestamp": "2026-05-09T14:32:01Z",
    "hostname": "myserver",
    "cpu": { "percent": 41.2, "count_logical": 8, ... },
    "memory": { "percent": 61.4, "used_gb": 5.83, ... },
    "disk": [ { "path": "/", "percent": 48.3, ... } ],
    "network": { "bytes_sent_mb": 1432.55, ... },
    "top_processes": [ ... ]
  }
]
```

**`reports/metrics.csv`** — flat table, easy to open in Excel / import to Grafana:

```
timestamp,hostname,cpu_percent,memory_percent,swap_percent,disk_root_percent,...
2026-05-09T14:32:01Z,myserver,41.2,61.4,0.0,48.3,...
```

---

## Skills demonstrated

| Skill | Where |
|---|---|
| Python systems scripting | `monitor.py` — psutil, signal handling, argparse |
| Linux service management | `sysmon.service` — systemd unit, security hardening |
| Observability thinking | Metrics → export → alert → recover cycle |
| Configuration management | `config.yaml` — all tunables externalized |
| Clean code structure | Separate concerns: collectors, engine, exporters, UI |

---

## Requirements

- Linux (Ubuntu 20.04+ / Debian / Arch / RHEL)
- Python 3.8+
- `psutil` and `PyYAML` (installed via `requirements.txt`)

---

## Part of my DevOps portfolio

This is Lab 01 of a 15-project DevOps portfolio covering Linux, Python, Terraform, AWS, Docker, Kubernetes and CI/CD.

## Part of my DevOps portfolio

Install dependencies and run the dashboard: pip3 install flask, then python3 web.py

Open

Visual alerts and browser notifications

→ [View full portfolio](https://github.com/kt-it26)
