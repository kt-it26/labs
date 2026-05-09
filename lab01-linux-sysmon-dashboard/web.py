#!/usr/bin/env python3
"""
web.py — Flask dashboard for linux-sysmon-dashboard
Run: python3 web.py
Then open: http://localhost:5000
"""

from flask import Flask, jsonify, render_template_string, request
import psutil, yaml, json
from datetime import datetime
import os

app = Flask(__name__)
config = yaml.safe_load(open("config.yaml"))

# ── State (in-memory, resets on restart) ─────────────────────────────────────
state = {
    "watched_pids": [],        # PIDs the user selected to watch
    "thresholds": config.get("thresholds", {
        "cpu_percent": 75,
        "memory_percent": 80,
        "disk_percent": 80,
        "swap_percent": 50,
    }),
}

# ── API routes ────────────────────────────────────────────────────────────────

@app.route("/api/metrics")
def api_metrics():
    cpu    = psutil.cpu_percent(interval=0.5)
    mem    = psutil.virtual_memory()
    disk   = psutil.disk_usage("/")
    swap   = psutil.swap_memory()
    net    = psutil.net_io_counters()

    procs = []
    for p in psutil.process_iter(["pid","name","cpu_percent","memory_percent","status"]):
        try:
            info = p.info
            info["watched"] = info["pid"] in state["watched_pids"]
            procs.append(info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    watched_metrics = []
    for pid in state["watched_pids"]:
        try:
            p = psutil.Process(pid)
            watched_metrics.append({
                "pid": pid,
                "name": p.name(),
                "cpu_percent": p.cpu_percent(interval=0.1),
                "memory_percent": round(p.memory_percent(), 2),
                "status": p.status(),
            })
        except psutil.NoSuchProcess:
            state["watched_pids"].remove(pid)

    t = state["thresholds"]
    alerts = []
    if cpu          >= t.get("cpu_percent",   75): alerts.append(f"CPU al {cpu:.1f}%")
    if mem.percent  >= t.get("memory_percent", 80): alerts.append(f"RAM al {mem.percent:.1f}%")
    if disk.percent >= t.get("disk_percent",   80): alerts.append(f"Disco al {disk.percent:.1f}%")
    if swap.percent >= t.get("swap_percent",   50): alerts.append(f"Swap al {swap.percent:.1f}%")

    return jsonify({
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "cpu":    {"percent": cpu, "cores": psutil.cpu_count()},
        "memory": {"percent": mem.percent,  "used_gb": round(mem.used/1e9,2), "total_gb": round(mem.total/1e9,2)},
        "disk":   {"percent": disk.percent, "free_gb": round(disk.free/1e9,2)},
        "swap":   {"percent": swap.percent},
        "network":{"sent_mb": round(net.bytes_sent/1e6,2), "recv_mb": round(net.bytes_recv/1e6,2)},
        "processes": sorted(procs, key=lambda x: x.get("cpu_percent") or 0, reverse=True)[:50],
        "watched": watched_metrics,
        "alerts":  alerts,
        "thresholds": state["thresholds"],
    })


@app.route("/api/watch", methods=["POST"])
def api_watch():
    pid = request.json.get("pid")
    if pid in state["watched_pids"]:
        state["watched_pids"].remove(pid)
        return jsonify({"status": "removed", "pid": pid})
    state["watched_pids"].append(pid)
    return jsonify({"status": "added", "pid": pid})


@app.route("/api/thresholds", methods=["POST"])
def api_thresholds():
    data = request.json
    for key in ["cpu_percent","memory_percent","disk_percent","swap_percent"]:
        if key in data:
            state["thresholds"][key] = int(data[key])
    return jsonify({"status": "ok", "thresholds": state["thresholds"]})


# ── Main page ─────────────────────────────────────────────────────────────────

HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>sysmon · kt-it26</title>
<style>
  :root {
    --bg:        #0f0f0f;
    --surface:   #1a1a1a;
    --border:    #2a2a2a;
    --green:     #4ade80;
    --green-dim: #166534;
    --silver:    #cbd5e1;
    --silver-dim:#475569;
    --text:      #e2e8f0;
    --muted:     #64748b;
    --alert:     #ef4444;
    --radius:    12px;
    --font:      -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', sans-serif;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: var(--font); font-size: 14px; min-height: 100vh; }

  /* ── Topbar ── */
  .topbar {
    display: flex; align-items: center; justify-content: space-between;
    padding: 14px 28px;
    background: var(--surface);
    border-bottom: 0.5px solid var(--border);
    position: sticky; top: 0; z-index: 100;
  }
  .topbar-left { display: flex; align-items: center; gap: 10px; }
  .dot { width: 12px; height: 12px; border-radius: 50%; }
  .dot-red    { background: #ff5f57; }
  .dot-yellow { background: #ffbd2e; }
  .dot-green  { background: #28c840; }
  .logo { font-size: 15px; font-weight: 600; color: var(--green); letter-spacing: -0.3px; margin-left: 16px; }
  .timestamp { font-size: 12px; color: var(--muted); }
  .signature { font-size: 12px; color: var(--silver-dim); letter-spacing: 0.05em; }

  /* ── Layout ── */
  .main { padding: 24px 28px; max-width: 1200px; margin: 0 auto; }
  .grid-4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; }
  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 20px; }

  /* ── Cards ── */
  .card {
    background: var(--surface);
    border: 0.5px solid var(--border);
    border-radius: var(--radius);
    padding: 16px 20px;
  }
  .card-label { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px; }
  .card-value { font-size: 28px; font-weight: 300; color: var(--silver); letter-spacing: -1px; }
  .card-sub   { font-size: 12px; color: var(--muted); margin-top: 4px; }

  /* ── Progress bar ── */
  .bar-wrap { background: #222; border-radius: 99px; height: 5px; margin-top: 10px; overflow: hidden; }
  .bar-fill { height: 5px; border-radius: 99px; transition: width 0.6s ease; background: var(--green); }
  .bar-fill.warn  { background: #facc15; }
  .bar-fill.alert { background: var(--alert); }

  /* ── Section title ── */
  .section-title {
    font-size: 11px; color: var(--muted); text-transform: uppercase;
    letter-spacing: 0.08em; margin-bottom: 12px; padding-bottom: 8px;
    border-bottom: 0.5px solid var(--border);
  }

  /* ── Thresholds panel ── */
  .threshold-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .threshold-item { display: flex; flex-direction: column; gap: 6px; }
  .threshold-item label { font-size: 12px; color: var(--silver-dim); }
  .threshold-row { display: flex; align-items: center; gap: 10px; }
  .threshold-row input[type=range] {
    flex: 1; accent-color: var(--green); height: 4px;
    background: #333; border-radius: 99px; outline: none;
    -webkit-appearance: none;
  }
  .threshold-val { font-size: 13px; color: var(--green); min-width: 36px; text-align: right; font-weight: 500; }
  .btn-apply {
    margin-top: 14px; padding: 8px 20px;
    background: var(--green-dim); color: var(--green);
    border: 0.5px solid var(--green); border-radius: 8px;
    cursor: pointer; font-size: 13px; transition: background 0.15s;
  }
  .btn-apply:hover { background: #14532d; }

  /* ── Alerts ── */
  .alert-bar {
    background: #1c0a0a; border: 0.5px solid #7f1d1d;
    border-radius: var(--radius); padding: 12px 16px;
    margin-bottom: 16px; display: none;
  }
  .alert-bar.visible { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
  .alert-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--alert); flex-shrink: 0; animation: pulse 1.5s infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }
  .alert-text { font-size: 13px; color: #fca5a5; }

  /* ── Process table ── */
  .proc-table { width: 100%; border-collapse: collapse; }
  .proc-table th {
    text-align: left; font-size: 11px; color: var(--muted);
    text-transform: uppercase; letter-spacing: 0.06em;
    padding: 0 10px 10px 0; font-weight: 400;
  }
  .proc-table td { padding: 7px 10px 7px 0; border-top: 0.5px solid var(--border); font-size: 13px; vertical-align: middle; }
  .proc-table tr:hover td { background: #1f1f1f; }
  .proc-name { color: var(--silver); font-weight: 500; max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .proc-pid  { color: var(--muted); font-size: 12px; font-family: monospace; }
  .watch-btn {
    font-size: 11px; padding: 3px 10px; border-radius: 6px; cursor: pointer;
    border: 0.5px solid var(--border); background: transparent; color: var(--muted);
    transition: all 0.15s;
  }
  .watch-btn.active { border-color: var(--green); color: var(--green); background: var(--green-dim); }
  .watch-btn:hover  { border-color: var(--silver-dim); color: var(--silver); }

  /* ── Watched processes ── */
  .watched-list { display: flex; flex-direction: column; gap: 10px; }
  .watched-item { display: flex; align-items: center; gap: 12px; }
  .watched-name { color: var(--silver); font-weight: 500; width: 140px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .watched-bar-wrap { flex: 1; }
  .watched-pct { font-size: 12px; color: var(--green); min-width: 40px; text-align: right; }
  .empty-state { color: var(--muted); font-size: 13px; padding: 12px 0; }

  /* ── Network card ── */
  .net-row { display: flex; justify-content: space-between; margin-top: 10px; }
  .net-item { text-align: center; }
  .net-val { font-size: 20px; font-weight: 300; color: var(--silver); }
  .net-lbl { font-size: 11px; color: var(--muted); margin-top: 2px; }

  /* ── Footer ── */
  .footer { text-align: center; padding: 24px; font-size: 12px; color: var(--muted); border-top: 0.5px solid var(--border); margin-top: 8px; }
  .footer span { color: var(--green); }
</style>
</head>
<body>

<div class="topbar">
  <div class="topbar-left">
    <div class="dot dot-red"></div>
    <div class="dot dot-yellow"></div>
    <div class="dot dot-green"></div>
    <div class="logo">sysmon</div>
  </div>
  <div class="timestamp" id="ts">--:--:--</div>
  <div class="signature">kt-it26</div>
</div>

<div class="main">

  <!-- Alerts -->
  <div class="alert-bar" id="alert-bar">
    <div class="alert-dot"></div>
    <div class="alert-text" id="alert-text"></div>
  </div>

  <!-- Metric cards -->
  <div class="grid-4">
    <div class="card">
      <div class="card-label">CPU</div>
      <div class="card-value" id="cpu-val">--%</div>
      <div class="card-sub" id="cpu-sub">-- cores</div>
      <div class="bar-wrap"><div class="bar-fill" id="cpu-bar" style="width:0%"></div></div>
    </div>
    <div class="card">
      <div class="card-label">Memory</div>
      <div class="card-value" id="mem-val">--%</div>
      <div class="card-sub" id="mem-sub">-- / -- GB</div>
      <div class="bar-wrap"><div class="bar-fill" id="mem-bar" style="width:0%"></div></div>
    </div>
    <div class="card">
      <div class="card-label">Disk /</div>
      <div class="card-value" id="disk-val">--%</div>
      <div class="card-sub" id="disk-sub">-- GB free</div>
      <div class="bar-wrap"><div class="bar-fill" id="disk-bar" style="width:0%"></div></div>
    </div>
    <div class="card">
      <div class="card-label">Swap</div>
      <div class="card-value" id="swap-val">--%</div>
      <div class="card-sub">virtual memory</div>
      <div class="bar-wrap"><div class="bar-fill" id="swap-bar" style="width:0%"></div></div>
    </div>
  </div>

  <div class="grid-2">

    <!-- Network -->
    <div class="card">
      <div class="section-title">Network</div>
      <div class="net-row">
        <div class="net-item">
          <div class="net-val" id="net-sent">-- MB</div>
          <div class="net-lbl">Enviado</div>
        </div>
        <div class="net-item">
          <div class="net-val" id="net-recv">-- MB</div>
          <div class="net-lbl">Recibido</div>
        </div>
      </div>
    </div>

    <!-- Thresholds -->
    <div class="card">
      <div class="section-title">Umbrales de alerta</div>
      <div class="threshold-grid">
        <div class="threshold-item">
          <label>CPU %</label>
          <div class="threshold-row">
            <input type="range" min="10" max="100" value="75" id="thr-cpu" oninput="document.getElementById('v-cpu').textContent=this.value+'%'">
            <span class="threshold-val" id="v-cpu">75%</span>
          </div>
        </div>
        <div class="threshold-item">
          <label>RAM %</label>
          <div class="threshold-row">
            <input type="range" min="10" max="100" value="80" id="thr-mem" oninput="document.getElementById('v-mem').textContent=this.value+'%'">
            <span class="threshold-val" id="v-mem">80%</span>
          </div>
        </div>
        <div class="threshold-item">
          <label>Disco %</label>
          <div class="threshold-row">
            <input type="range" min="10" max="100" value="80" id="thr-disk" oninput="document.getElementById('v-disk').textContent=this.value+'%'">
            <span class="threshold-val" id="v-disk">80%</span>
          </div>
        </div>
        <div class="threshold-item">
          <label>Swap %</label>
          <div class="threshold-row">
            <input type="range" min="10" max="100" value="50" id="thr-swap" oninput="document.getElementById('v-swap').textContent=this.value+'%'">
            <span class="threshold-val" id="v-swap">50%</span>
          </div>
        </div>
      </div>
      <button class="btn-apply" onclick="applyThresholds()">Aplicar umbrales</button>
    </div>

  </div>

  <div class="grid-2">

    <!-- Watched processes -->
    <div class="card">
      <div class="section-title">Procesos monitoreados</div>
      <div class="watched-list" id="watched-list">
        <div class="empty-state">Seleccioná procesos en la tabla →</div>
      </div>
    </div>

    <!-- Process list -->
    <div class="card">
      <div class="section-title">Todos los procesos (top 50 por CPU)</div>
      <div style="overflow-x:auto; max-height: 340px; overflow-y: auto;">
        <table class="proc-table">
          <thead>
            <tr>
              <th>Nombre</th>
              <th>PID</th>
              <th>CPU%</th>
              <th>RAM%</th>
              <th></th>
            </tr>
          </thead>
          <tbody id="proc-tbody"></tbody>
        </table>
      </div>
    </div>

  </div>

</div>

<div class="footer">
  lab01 · linux-sysmon-dashboard · <span>kt-it26</span> · 2026
</div>

<script>
let watchedPids = new Set();

function barClass(pct, threshold) {
  if (pct >= threshold)       return 'bar-fill alert';
  if (pct >= threshold * 0.8) return 'bar-fill warn';
  return 'bar-fill';
}

async function fetchMetrics() {
  try {
    const r = await fetch('/api/metrics');
    const d = await r.json();
    const t = d.thresholds;

    document.getElementById('ts').textContent = d.timestamp;

    // CPU
    document.getElementById('cpu-val').textContent = d.cpu.percent.toFixed(1) + '%';
    document.getElementById('cpu-sub').textContent = d.cpu.cores + ' cores';
    const cpuBar = document.getElementById('cpu-bar');
    cpuBar.style.width = d.cpu.percent + '%';
    cpuBar.className = barClass(d.cpu.percent, t.cpu_percent);

    // Memory
    document.getElementById('mem-val').textContent = d.memory.percent.toFixed(1) + '%';
    document.getElementById('mem-sub').textContent = d.memory.used_gb + ' / ' + d.memory.total_gb + ' GB';
    const memBar = document.getElementById('mem-bar');
    memBar.style.width = d.memory.percent + '%';
    memBar.className = barClass(d.memory.percent, t.memory_percent);

    // Disk
    document.getElementById('disk-val').textContent = d.disk.percent.toFixed(1) + '%';
    document.getElementById('disk-sub').textContent = d.disk.free_gb + ' GB free';
    const diskBar = document.getElementById('disk-bar');
    diskBar.style.width = d.disk.percent + '%';
    diskBar.className = barClass(d.disk.percent, t.disk_percent);

    // Swap
    document.getElementById('swap-val').textContent = d.swap.percent.toFixed(1) + '%';
    const swapBar = document.getElementById('swap-bar');
    swapBar.style.width = d.swap.percent + '%';
    swapBar.className = barClass(d.swap.percent, t.swap_percent);

    // Network
    document.getElementById('net-sent').textContent = d.network.sent_mb.toFixed(1) + ' MB';
    document.getElementById('net-recv').textContent = d.network.recv_mb.toFixed(1) + ' MB';

    // Alerts
    const alertBar = document.getElementById('alert-bar');
    if (d.alerts.length > 0) {
      alertBar.classList.add('visible');
      document.getElementById('alert-text').textContent = d.alerts.join('  ·  ');
      if (Notification.permission === 'granted') {
        new Notification('sysmon alert', { body: d.alerts.join(', ') });
      }
    } else {
      alertBar.classList.remove('visible');
    }

    // Process table
    const tbody = document.getElementById('proc-tbody');
    tbody.innerHTML = '';
    d.processes.forEach(p => {
      const isWatched = watchedPids.has(p.pid);
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><span class="proc-name" title="${p.name}">${p.name || '?'}</span></td>
        <td><span class="proc-pid">${p.pid}</span></td>
        <td>${(p.cpu_percent || 0).toFixed(1)}</td>
        <td>${(p.memory_percent || 0).toFixed(1)}</td>
        <td><button class="watch-btn ${isWatched ? 'active' : ''}"
          onclick="toggleWatch(${p.pid}, this)">
          ${isWatched ? 'watching' : 'watch'}
        </button></td>`;
      tbody.appendChild(tr);
    });

    // Watched panel
    const wl = document.getElementById('watched-list');
    if (d.watched.length === 0) {
      wl.innerHTML = '<div class="empty-state">Seleccioná procesos en la tabla →</div>';
    } else {
      wl.innerHTML = d.watched.map(p => `
        <div class="watched-item">
          <span class="watched-name" title="${p.name}">${p.name}</span>
          <div class="watched-bar-wrap">
            <div class="bar-wrap">
              <div class="bar-fill" style="width:${Math.min(p.cpu_percent,100)}%"></div>
            </div>
          </div>
          <span class="watched-pct">${p.cpu_percent.toFixed(1)}%</span>
        </div>`).join('');
    }

  } catch(e) { console.error(e); }
}

async function toggleWatch(pid, btn) {
  const r = await fetch('/api/watch', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({pid})
  });
  const d = await r.json();
  if (d.status === 'added') {
    watchedPids.add(pid);
    btn.textContent = 'watching';
    btn.classList.add('active');
  } else {
    watchedPids.delete(pid);
    btn.textContent = 'watch';
    btn.classList.remove('active');
  }
}

async function applyThresholds() {
  await fetch('/api/thresholds', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({
      cpu_percent:    parseInt(document.getElementById('thr-cpu').value),
      memory_percent: parseInt(document.getElementById('thr-mem').value),
      disk_percent:   parseInt(document.getElementById('thr-disk').value),
      swap_percent:   parseInt(document.getElementById('thr-swap').value),
    })
  });
}

if (Notification.permission === 'default') Notification.requestPermission();

fetchMetrics();
setInterval(fetchMetrics, 3000);
</script>
</body>
</html>"""

@app.route("/")
def index():
    return render_template_string(HTML)


if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 5000))
    print(f"\n  sysmon web · kt-it26")
    print(f"  http://localhost:{port}\n")
    app.run(host=host, port=port, debug=False)