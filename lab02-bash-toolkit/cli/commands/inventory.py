"""
cli/commands/inventory.py — complete system inventory snapshot
OS, hardware, packages, services, users, network interfaces, cron jobs
"""

import os
import subprocess
import platform
import socket
from pathlib import Path
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from cli.utils import *

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


def run(cmd: list) -> str:
    try:
        return subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def get_os_info() -> dict:
    return {
        "hostname":     socket.gethostname(),
        "os":           platform.system(),
        "distro":       run(["lsb_release", "-ds"]) or platform.version(),
        "kernel":       platform.release(),
        "arch":         platform.machine(),
        "python":       platform.python_version(),
        "uptime":       run(["uptime", "-p"]),
        "timezone":     run(["timedatectl", "show", "--property=Timezone", "--value"]),
    }


def get_hardware() -> dict:
    hw = {
        "cpu_model":    run(["grep", "-m1", "model name", "/proc/cpuinfo"]).split(":")[-1].strip(),
        "cpu_cores":    run(["nproc"]),
        "total_ram":    "",
        "disks":        [],
    }
    if HAS_PSUTIL:
        import psutil
        hw["total_ram"] = human_size(psutil.virtual_memory().total)
        for part in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(part.mountpoint)
                hw["disks"].append({
                    "device":     part.device,
                    "mountpoint": part.mountpoint,
                    "fstype":     part.fstype,
                    "total":      human_size(usage.total),
                    "used":       human_size(usage.used),
                    "free":       human_size(usage.free),
                    "percent":    usage.percent,
                })
            except PermissionError:
                pass
    return hw


def get_network_interfaces() -> list:
    interfaces = []
    if HAS_PSUTIL:
        import psutil
        addrs = psutil.net_if_addrs()
        stats = psutil.net_if_stats()
        for iface, addr_list in addrs.items():
            iface_stat = stats.get(iface)
            ips = [a.address for a in addr_list if a.family.name in ("AF_INET","AF_INET6")]
            interfaces.append({
                "interface": iface,
                "ips":       ips,
                "up":        iface_stat.isup if iface_stat else None,
                "speed_mb":  iface_stat.speed if iface_stat else None,
            })
    return interfaces


def get_installed_packages(full: bool = False) -> list:
    pkgs = []
    # Try dpkg (Debian/Ubuntu)
    raw = run(["dpkg", "--get-selections"])
    if raw:
        for line in raw.splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[1] == "install":
                pkgs.append(parts[0])
        if not full:
            pkgs = pkgs[:100]  # cap at 100 unless --full
    # Fallback: rpm
    elif not pkgs:
        raw = run(["rpm", "-qa", "--qf", "%{NAME}\n"])
        pkgs = raw.splitlines()[:100]
    return pkgs


def get_running_services() -> list:
    raw = run(["systemctl", "list-units", "--type=service", "--state=running", "--no-pager", "--plain"])
    services = []
    for line in raw.splitlines()[1:]:
        parts = line.split()
        if parts and parts[0].endswith(".service"):
            services.append({
                "name":   parts[0].replace(".service", ""),
                "status": parts[2] if len(parts) > 2 else "?",
                "description": " ".join(parts[4:]) if len(parts) > 4 else "",
            })
    return services


def get_users() -> list:
    users = []
    try:
        with open("/etc/passwd") as f:
            for line in f:
                parts = line.strip().split(":")
                if len(parts) >= 7 and parts[6] not in ("/bin/false", "/usr/sbin/nologin"):
                    users.append({
                        "username": parts[0],
                        "uid":      parts[2],
                        "home":     parts[5],
                        "shell":    parts[6],
                    })
    except PermissionError:
        pass
    return users


def get_cron_jobs() -> list:
    jobs = []
    cron_dirs = ["/etc/cron.d", "/etc/cron.daily", "/etc/cron.hourly", "/etc/cron.weekly"]
    for d in cron_dirs:
        p = Path(d)
        if p.exists():
            for f in p.iterdir():
                if f.is_file():
                    jobs.append({"file": str(f), "dir": d})
    return jobs


def get_open_ports() -> list:
    raw = run(["ss", "-tlnp"])
    ports = []
    for line in raw.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 4:
            local = parts[3]
            ports.append({"local_address": local, "raw": line.strip()})
    return ports


def cmd_inventory(args):
    header("SYSTEM INVENTORY SNAPSHOT")
    info(f"Collecting full system inventory...")
    print()

    inventory = {"generated_at": now_str(), "generated_by": "kt-it26/lab02-bash-toolkit"}

    info("OS & platform...")
    inventory["os"] = get_os_info()
    ok(f"OS: {inventory['os']['distro']} | Kernel: {inventory['os']['kernel']}")

    info("Hardware...")
    inventory["hardware"] = get_hardware()
    ok(f"CPU: {inventory['hardware']['cpu_model']} ({inventory['hardware']['cpu_cores']} cores)")
    ok(f"RAM: {inventory['hardware']['total_ram']}")

    info("Network interfaces...")
    inventory["network_interfaces"] = get_network_interfaces()
    ok(f"Interfaces: {len(inventory['network_interfaces'])} found")

    info("Running services...")
    inventory["services"] = get_running_services()
    ok(f"Running services: {len(inventory['services'])}")

    info("Open ports...")
    inventory["open_ports"] = get_open_ports()
    ok(f"Listening ports: {len(inventory['open_ports'])}")

    info("Users with shell access...")
    inventory["users"] = get_users()
    ok(f"Shell users: {len(inventory['users'])}")

    info("Cron jobs...")
    inventory["cron_jobs"] = get_cron_jobs()
    ok(f"Cron entries: {len(inventory['cron_jobs'])}")

    info(f"Installed packages (full={args.full})...")
    inventory["packages"] = get_installed_packages(full=args.full)
    ok(f"Packages: {len(inventory['packages'])}{'+ (capped, use --full for all)' if not args.full else ''}")

    print()
    # Print summary table
    rows = [
        {"section": "OS",           "value": f"{inventory['os']['distro']}"},
        {"section": "Kernel",       "value": inventory['os']['kernel']},
        {"section": "Uptime",       "value": inventory['os']['uptime']},
        {"section": "CPU",          "value": f"{inventory['hardware']['cpu_cores']} cores"},
        {"section": "RAM",          "value": inventory['hardware']['total_ram']},
        {"section": "Disks",        "value": f"{len(inventory['hardware']['disks'])} mount points"},
        {"section": "Net ifaces",   "value": str(len(inventory['network_interfaces']))},
        {"section": "Services",     "value": f"{len(inventory['services'])} running"},
        {"section": "Packages",     "value": f"{len(inventory['packages'])} found"},
        {"section": "Shell users",  "value": str(len(inventory['users']))},
    ]
    table(rows, ["section", "value"])

    save_json(inventory, args.output)
    ok(f"Full inventory → {args.output}")
