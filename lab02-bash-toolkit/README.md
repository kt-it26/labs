# lab02-bash-toolkit

A unified DevOps CLI toolkit for Linux systems administration — built with Python and Bash. Six real-world automation tools in one command, generating structured JSON output and a full HTML report.

**Lab 02** of my DevOps portfolio · kt-it26

---

## What it does

| Command | What it automates |
|---|---|
| `devops logs` | Rotate, compress and archive log files with configurable size limits |
| `devops backup` | Smart directory backup with SHA256 integrity verification |
| `devops health` | Port scanner with latency tracking and persistent history |
| `devops inventory` | Full system snapshot: OS, hardware, packages, services, users, ports |
| `devops watchdog` | Service monitor with auto-restart on failure |
| `devops report` | Generate a full HTML report from all collected data |

---

## Quick start

```bash
git clone https://github.com/kt-it26/lab02-bash-toolkit
cd lab02-bash-toolkit
pip3 install -r requirements.txt
python3 -m cli.main --help
```

---

## Usage

```bash
# Rotate logs over 50MB, keep 7 copies, compress them
python3 -m cli.main logs --dir /var/log --max-size 50 --keep 7 --compress

# Backup with integrity check
python3 -m cli.main backup --src /home/user --dest /backup --compress --verify

# Scan ports once
python3 -m cli.main health --ports 22,80,443,3306,5432 --host localhost

# Scan every 30 seconds continuously
python3 -m cli.main health --ports 22,80,443 --interval 30

# Full system inventory
python3 -m cli.main inventory --output reports/inventory.json

# Full inventory including all packages
python3 -m cli.main inventory --full

# Watch services, auto-restart if they go down (needs sudo)
sudo python3 -m cli.main watchdog --services nginx,postgresql,redis --restart --interval 10

# Generate HTML report from all collected data
python3 -m cli.main report --output reports/report.html --open

# Bash scripts (no Python needed)
bash scripts/log-rotate.sh /var/log 50 7
bash scripts/backup.sh /home/user /backup yes
bash scripts/port-health.sh localhost 22,80,443,3306
```

---

## Project structure

```
lab02-bash-toolkit/
├── cli/
│   ├── main.py                 # Unified CLI entry point
│   ├── utils.py                # Shared helpers, pretty-print, colors
│   └── commands/
│       ├── logs.py             # Log rotation engine
│       ├── backup.py           # Smart backup + SHA256 integrity
│       ├── health.py           # Port scanner with history
│       ├── inventory.py        # Full system inventory
│       ├── watchdog.py         # Service watchdog + auto-restart
│       └── report.py           # HTML report generator
├── scripts/
│   ├── log-rotate.sh           # Native bash log rotation
│   ├── backup.sh               # Native bash backup
│   └── port-health.sh          # Native bash port checker
├── reports/                    # Generated output (git-ignored)
├── crontab.example             # Ready-to-use cron schedules
├── requirements.txt
└── README.md
```

---

## Output

Every command saves structured JSON to `reports/`. The `report` command reads all of them and produces a styled HTML document:

- System overview (OS, kernel, uptime, hardware)
- Disk usage with visual bars
- Network interfaces
- Port health results
- Running services list
- Installed packages index
- Backup manifest with integrity status
- Watchdog event log

---

## Skills demonstrated

| Skill | Where |
|---|---|
| Python CLI architecture | `cli/main.py` — argparse, subcommands, dispatch table |
| Modular code design | Each command is an independent module with shared utils |
| Bash scripting | `scripts/` — native alternatives to every Python command |
| SHA256 integrity | `commands/backup.py` — file-by-file checksum comparison |
| System introspection | `commands/inventory.py` — psutil + subprocess + /proc |
| Cron automation | `crontab.example` — production-ready schedules |
| HTML report generation | `commands/report.py` — styled output from JSON data |

---

## Requirements

- Linux (Ubuntu 20.04+ recommended)
- Python 3.8+
- `psutil`, `PyYAML` (via `requirements.txt`)
- `systemctl` for watchdog and service inventory
- `sudo` for watchdog auto-restart and some log paths

---

## Part of my DevOps portfolio

→ [lab01-sysmon-agent](https://github.com/kt-it26/lab01-sysmon-agent) — real-time system monitor
→ [View all 15 labs](https://github.com/kt-it26)
            