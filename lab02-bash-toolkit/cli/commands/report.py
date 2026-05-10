"""
cli/commands/report.py — generate a stunning HTML report from all collected data
"""

import json
import os
import webbrowser
from pathlib import Path
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from cli.utils import *


def load_report_data() -> dict:
    data = {}
    files = {
        "inventory": "reports/inventory.json",
        "health":    "reports/health.json",
        "backup":    "reports/backup-manifest.json",
        "logs":      "reports/log-rotation.json",
        "watchdog":  "reports/watchdog.log",
    }
    for key, path in files.items():
        if Path(path).exists():
            if path.endswith(".json"):
                data[key] = load_json(path)
            else:
                with open(path) as f:
                    data[key] = f.read()
        else:
            data[key] = None
    return data


def generate_html(data: dict) -> str:
    inv      = data.get("inventory") or {}
    health   = data.get("health") or []
    backup   = data.get("backup") or {}
    logs     = data.get("logs") or {}
    watchdog = data.get("watchdog") or ""

    os_info  = inv.get("os", {})
    hw       = inv.get("hardware", {})
    services = inv.get("services", [])
    packages = inv.get("packages", [])
    users    = inv.get("users", [])
    ports    = inv.get("open_ports", [])
    disks    = hw.get("disks", [])
    ifaces   = inv.get("network_interfaces", [])

    # Health summary
    last_health = health[-1] if health else {}
    health_summary = last_health.get("summary", {})
    health_results = last_health.get("results", [])

    def service_rows():
        if not services:
            return "<tr><td colspan='3' style='color:var(--muted);padding:16px'>No service data — run: devops inventory</td></tr>"
        return "".join(f"""
        <tr>
          <td><span class='dot green'></span> {s['name']}</td>
          <td style='color:var(--muted)'>{s.get('status','?')}</td>
          <td style='color:var(--muted);font-size:12px'>{s.get('description','')[:50]}</td>
        </tr>""" for s in services[:20])

    def disk_rows():
        if not disks:
            return "<tr><td colspan='5' style='color:var(--muted);padding:16px'>No disk data</td></tr>"
        rows = ""
        for d in disks:
            pct = d.get('percent', 0)
            color = '#ef4444' if pct >= 80 else '#facc15' if pct >= 60 else '#4ade80'
            rows += f"""
        <tr>
          <td style='font-family:monospace'>{d['device']}</td>
          <td>{d['mountpoint']}</td>
          <td>{d['fstype']}</td>
          <td>{d['total']}</td>
          <td>
            <div style='display:flex;align-items:center;gap:8px'>
              <div style='flex:1;background:#222;border-radius:99px;height:4px'>
                <div style='width:{pct}%;background:{color};height:4px;border-radius:99px'></div>
              </div>
              <span style='color:{color};font-size:12px;min-width:36px'>{pct}%</span>
            </div>
          </td>
        </tr>"""
        return rows

    def health_rows():
        if not health_results:
            return "<tr><td colspan='4' style='color:var(--muted);padding:16px'>No health data — run: devops health</td></tr>"
        rows = ""
        for r in health_results:
            open_ = r['status'] == 'open'
            color = '#4ade80' if open_ else '#ef4444'
            dot   = '●' if open_ else '○'
            lat   = f"{r['latency_ms']:.1f} ms" if r.get('latency_ms') else '—'
            rows += f"""
        <tr>
          <td><span style='color:{color}'>{dot}</span> {r['port']}</td>
          <td>{r.get('service','?')}</td>
          <td style='color:{color}'>{r['status']}</td>
          <td style='color:var(--muted)'>{lat}</td>
        </tr>"""
        return rows

    def iface_rows():
        if not ifaces:
            return "<p style='color:var(--muted)'>No network data</p>"
        rows = ""
        for i in ifaces:
            ips = ", ".join(i.get("ips", []))
            up  = i.get("up")
            color = '#4ade80' if up else '#ef4444'
            rows += f"""
        <tr>
          <td style='font-weight:500'>{i['interface']}</td>
          <td style='font-family:monospace;font-size:12px'>{ips or '—'}</td>
          <td style='color:{color}'>{'up' if up else 'down'}</td>
          <td style='color:var(--muted)'>{i.get('speed_mb') or '?'} Mbps</td>
        </tr>"""
        return rows

    def package_tags():
        if not packages:
            return "<span style='color:var(--muted)'>No package data</span>"
        return "".join(f"<span class='pkg-tag'>{p}</span>" for p in packages[:80])

    def user_rows():
        if not users:
            return "<tr><td colspan='3' style='color:var(--muted);padding:16px'>No user data</td></tr>"
        return "".join(f"""
        <tr>
          <td style='font-weight:500'>{u['username']}</td>
          <td style='color:var(--muted);font-family:monospace;font-size:12px'>{u['home']}</td>
          <td style='color:var(--muted);font-family:monospace;font-size:12px'>{u['shell']}</td>
        </tr>""" for u in users)

    gen_time = now_str()
    hostname = os_info.get("hostname", "unknown")
    distro   = os_info.get("distro", "—")
    kernel   = os_info.get("kernel", "—")
    uptime   = os_info.get("uptime", "—")
    cpu      = hw.get("cpu_model", "—")
    cores    = hw.get("cpu_cores", "—")
    ram      = hw.get("total_ram", "—")
    pkg_count = len(packages)
    svc_count = len(services)

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>DevOps Report · {hostname} · kt-it26</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=DM+Sans:wght@300;400;500;600&display=swap');
:root {{
  --bg:       #0c0c0c;
  --surface:  #161616;
  --card:     #1c1c1c;
  --border:   #2a2a2a;
  --green:    #4ade80;
  --silver:   #cbd5e1;
  --muted:    #64748b;
  --text:     #e2e8f0;
  --red:      #ef4444;
  --yellow:   #facc15;
  --font:     'DM Sans', sans-serif;
  --mono:     'IBM Plex Mono', monospace;
  --radius:   14px;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ background: var(--bg); color: var(--text); font-family: var(--font); font-size: 14px; line-height: 1.6; }}

/* Top bar */
.topbar {{ background: var(--surface); border-bottom: 0.5px solid var(--border); padding: 16px 40px; display: flex; align-items: center; justify-content: space-between; position: sticky; top: 0; z-index: 100; backdrop-filter: blur(12px); }}
.topbar-dots {{ display: flex; gap: 7px; align-items: center; }}
.macos-dot {{ width: 13px; height: 13px; border-radius: 50%; }}
.title-group {{ display: flex; align-items: center; gap: 12px; }}
.report-title {{ font-size: 15px; font-weight: 600; color: var(--green); letter-spacing: -0.3px; }}
.report-host {{ font-size: 13px; color: var(--muted); font-family: var(--mono); }}
.report-time {{ font-size: 12px; color: var(--muted); font-family: var(--mono); }}
.sig {{ font-size: 12px; color: #334155; letter-spacing: 0.06em; font-family: var(--mono); }}

/* Layout */
.main {{ max-width: 1180px; margin: 0 auto; padding: 32px 40px 64px; }}
.section-title {{ font-size: 11px; text-transform: uppercase; letter-spacing: 0.1em; color: var(--muted); margin: 40px 0 16px; padding-bottom: 10px; border-bottom: 0.5px solid var(--border); font-family: var(--mono); }}
.section-title:first-child {{ margin-top: 0; }}
.grid-4 {{ display: grid; grid-template-columns: repeat(4,1fr); gap: 12px; margin-bottom: 12px; }}
.grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
.grid-1 {{ display: grid; grid-template-columns: 1fr; gap: 16px; }}

/* Stat cards */
.stat-card {{ background: var(--card); border: 0.5px solid var(--border); border-radius: var(--radius); padding: 20px 24px; }}
.stat-label {{ font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px; font-family: var(--mono); }}
.stat-value {{ font-size: 30px; font-weight: 300; color: var(--silver); letter-spacing: -1.5px; font-family: var(--mono); }}
.stat-sub {{ font-size: 12px; color: var(--muted); margin-top: 6px; }}

/* Tables */
.card {{ background: var(--card); border: 0.5px solid var(--border); border-radius: var(--radius); padding: 20px 24px; }}
table {{ width: 100%; border-collapse: collapse; }}
th {{ text-align: left; font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.06em; padding: 0 12px 12px 0; font-weight: 400; font-family: var(--mono); }}
td {{ padding: 10px 12px 10px 0; border-top: 0.5px solid var(--border); font-size: 13px; vertical-align: middle; }}
tr:hover td {{ background: rgba(255,255,255,0.02); }}
.dot {{ display: inline-block; width: 7px; height: 7px; border-radius: 50%; margin-right: 6px; }}
.dot.green {{ background: var(--green); }}
.dot.red   {{ background: var(--red); }}

/* Packages */
.pkg-wrap {{ display: flex; flex-wrap: wrap; gap: 6px; max-height: 300px; overflow-y: auto; }}
.pkg-tag {{ font-family: var(--mono); font-size: 11px; padding: 3px 10px; background: #1a1a1a; border: 0.5px solid var(--border); border-radius: 6px; color: var(--muted); }}
.pkg-tag:hover {{ border-color: var(--green); color: var(--green); }}

/* Watchdog log */
.log-block {{ font-family: var(--mono); font-size: 12px; background: var(--surface); border-radius: 10px; padding: 16px; max-height: 260px; overflow-y: auto; color: var(--muted); line-height: 1.8; white-space: pre-wrap; }}

/* Backup */
.backup-kv {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }}
.kv-item {{ background: var(--surface); border-radius: 8px; padding: 10px 14px; }}
.kv-label {{ font-size: 11px; color: var(--muted); font-family: var(--mono); margin-bottom: 4px; }}
.kv-val {{ font-size: 14px; color: var(--silver); font-weight: 500; }}

/* Footer */
.footer {{ text-align: center; padding: 48px 0 24px; font-size: 12px; color: var(--muted); font-family: var(--mono); border-top: 0.5px solid var(--border); margin-top: 48px; }}
.footer strong {{ color: var(--green); }}
</style>
</head>
<body>

<div class="topbar">
  <div style="display:flex;align-items:center;gap:20px">
    <div class="topbar-dots">
      <div class="macos-dot" style="background:#ff5f57"></div>
      <div class="macos-dot" style="background:#ffbd2e"></div>
      <div class="macos-dot" style="background:#28c840"></div>
    </div>
    <div class="title-group">
      <span class="report-title">DevOps Report</span>
      <span class="report-host">{hostname}</span>
    </div>
  </div>
  <span class="report-time">{gen_time}</span>
  <span class="sig">kt-it26</span>
</div>

<div class="main">

  <div class="section-title">System Overview</div>
  <div class="grid-4">
    <div class="stat-card">
      <div class="stat-label">Hostname</div>
      <div class="stat-value" style="font-size:20px">{hostname}</div>
      <div class="stat-sub">{distro}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Kernel</div>
      <div class="stat-value" style="font-size:20px">{kernel[:20]}</div>
      <div class="stat-sub">Uptime: {uptime}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">CPU</div>
      <div class="stat-value">{cores}</div>
      <div class="stat-sub">cores · {(cpu[:30] + '…') if len(cpu)>30 else cpu}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">RAM</div>
      <div class="stat-value" style="font-size:22px">{ram}</div>
      <div class="stat-sub">physical memory</div>
    </div>
  </div>
  <div class="grid-4">
    <div class="stat-card">
      <div class="stat-label">Services running</div>
      <div class="stat-value">{svc_count}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Packages installed</div>
      <div class="stat-value">{pkg_count}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Open ports scanned</div>
      <div class="stat-value">{health_summary.get('total', '—')}</div>
      <div class="stat-sub">{health_summary.get('open','—')} open · {health_summary.get('closed','—')} closed</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Backup files</div>
      <div class="stat-value">{backup.get('files', '—')}</div>
      <div class="stat-sub">{backup.get('size_human','—')}</div>
    </div>
  </div>

  <div class="section-title">Disk Usage</div>
  <div class="card">
    <table><thead><tr><th>Device</th><th>Mountpoint</th><th>FS</th><th>Total</th><th>Usage</th></tr></thead>
    <tbody>{disk_rows()}</tbody></table>
  </div>

  <div class="section-title">Network Interfaces</div>
  <div class="card">
    <table><thead><tr><th>Interface</th><th>IP Addresses</th><th>Status</th><th>Speed</th></tr></thead>
    <tbody>{iface_rows()}</tbody></table>
  </div>

  <div class="section-title">Port Health Scan</div>
  <div class="card">
    <table><thead><tr><th>Port</th><th>Service</th><th>Status</th><th>Latency</th></tr></thead>
    <tbody>{health_rows()}</tbody></table>
  </div>

  <div class="grid-2">
    <div>
      <div class="section-title">Running Services (top 20)</div>
      <div class="card">
        <table><thead><tr><th>Name</th><th>State</th><th>Description</th></tr></thead>
        <tbody>{service_rows()}</tbody></table>
      </div>
    </div>
    <div>
      <div class="section-title">Shell Users</div>
      <div class="card">
        <table><thead><tr><th>Username</th><th>Home</th><th>Shell</th></tr></thead>
        <tbody>{user_rows()}</tbody></table>
      </div>
    </div>
  </div>

  <div class="section-title">Backup Manifest</div>
  <div class="card">
    <div class="backup-kv">
      <div class="kv-item"><div class="kv-label">Timestamp</div><div class="kv-val">{backup.get('timestamp','—')}</div></div>
      <div class="kv-item"><div class="kv-label">Source</div><div class="kv-val">{backup.get('source','—')}</div></div>
      <div class="kv-item"><div class="kv-label">Destination</div><div class="kv-val">{(backup.get('destination','—') or '')[-60:]}</div></div>
      <div class="kv-item"><div class="kv-label">Size</div><div class="kv-val">{backup.get('size_human','—')}</div></div>
      <div class="kv-item"><div class="kv-label">Compressed</div><div class="kv-val">{'Yes' if backup.get('compressed') else 'No'}</div></div>
      <div class="kv-item"><div class="kv-label">Integrity</div><div class="kv-val" style="color:{'#4ade80' if backup.get('integrity')=='PASSED' else '#ef4444' if backup.get('integrity')=='FAILED' else '#64748b'}">{backup.get('integrity','—')}</div></div>
    </div>
  </div>

  <div class="section-title">Installed Packages ({pkg_count})</div>
  <div class="card">
    <div class="pkg-wrap">{package_tags()}</div>
  </div>

  <div class="section-title">Watchdog Log</div>
  <div class="card">
    <div class="log-block">{watchdog if watchdog else 'No watchdog log yet — run: devops watchdog --services nginx,ssh'}</div>
  </div>

</div>

<div class="footer">
  Generated by <strong>lab02-bash-toolkit</strong> · <strong>kt-it26</strong> · {gen_time}
</div>
</body>
</html>"""


def cmd_report(args):
    header("HTML REPORT GENERATOR")
    info("Loading collected data from reports/...")

    data = load_report_data()

    loaded = [k for k, v in data.items() if v is not None]
    missing = [k for k, v in data.items() if v is None]

    ok(f"Loaded  : {', '.join(loaded)}")
    if missing:
        warn(f"Missing : {', '.join(missing)} (run those commands first for complete report)")

    info("Generating HTML report...")
    html = generate_html(data)

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        f.write(html)

    size = Path(args.output).stat().st_size
    print()
    ok(f"Report generated → {args.output} ({human_size(size)})")
    info("Open in browser: devops report --open")

    if args.open:
        webbrowser.open(f"file://{os.path.abspath(args.output)}")
