"""
ai/analyzer.py — AI-powered scan analysis using Claude API
Analyzes scan results, detects anomalies, generates remediation advice
"""

import json
import urllib.request
import urllib.error
from datetime import datetime


CLAUDE_API = "https://api.anthropic.com/v1/messages"
MODEL      = "claude-sonnet-4-20250514"


def _call_claude(system: str, user: str, max_tokens: int = 1000) -> str:
    """Call Claude API. Returns text or error string."""
    payload = json.dumps({
        "model":      MODEL,
        "max_tokens": max_tokens,
        "system":     system,
        "messages":   [{"role": "user", "content": user}],
    }).encode()

    req = urllib.request.Request(
        CLAUDE_API,
        data    = payload,
        headers = {
            "Content-Type":      "application/json",
            "anthropic-version": "2023-06-01",
            # API key injected via env var at runtime — never hardcoded
        },
        method  = "POST",
    )

    # Inject key from environment
    import os
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return "_NO_API_KEY_"
    req.add_header("x-api-key", api_key)

    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
            return data["content"][0]["text"]
    except urllib.error.HTTPError as e:
        return f"_API_ERROR_{e.code}_"
    except Exception as e:
        return f"_ERROR_{e}_"


# ── Analysis functions ────────────────────────────────────────────────────────

def analyze_host(host_data: dict) -> dict:
    """
    Full AI analysis of a single scanned host.
    Returns: summary, threat_assessment, recommendations, anomalies
    """
    open_ports = host_data.get("open_ports", [])
    if not open_ports:
        return {
            "summary":         "Host is up but no open ports detected.",
            "threat_level":    "NONE",
            "anomalies":       [],
            "recommendations": [],
            "ai_available":    False,
        }

    # Build compact representation for the prompt
    port_summary = []
    for p in open_ports:
        cves = p.get("cves", [])
        cve_str = f" | CVEs: {', '.join(c['id'] for c in cves[:2])}" if cves else ""
        port_summary.append(
            f"  port={p['port']} service={p['service']} risk={p['risk']}"
            f" banner={p.get('banner','none')[:60] if p.get('banner') else 'none'}{cve_str}"
        )

    system = """You are a senior cybersecurity analyst and DevOps infrastructure expert.
Analyze network scan results and provide concise, actionable security assessments.
Always respond with valid JSON only — no markdown, no preamble.
Format: {"summary": "...", "threat_level": "NONE|LOW|MEDIUM|HIGH|CRITICAL",
"anomalies": ["...", "..."], "recommendations": ["...", "..."], "attack_vectors": ["..."]}"""

    user = f"""Analyze this host scan result:

Host: {host_data.get('ip')} ({host_data.get('hostname') or 'no rDNS'})
OS hint: {host_data.get('os_hint', 'unknown')}
Risk score: {host_data.get('risk_score', 0)} ({host_data.get('risk_level', 'UNKNOWN')})
Open ports:
{chr(10).join(port_summary)}

Identify security anomalies, likely attack vectors, and give 3-5 specific remediation steps.
Keep each recommendation under 15 words. Be direct and technical."""

    raw = _call_claude(system, user, max_tokens=800)

    if raw.startswith("_"):
        # AI unavailable — generate rule-based analysis
        return _rule_based_analysis(host_data)

    try:
        result = json.loads(raw)
        result["ai_available"] = True
        return result
    except json.JSONDecodeError:
        return _rule_based_analysis(host_data)


def analyze_network(hosts: list[dict]) -> dict:
    """
    Network-wide AI analysis — patterns, anomalies, executive summary.
    """
    if not hosts:
        return {"summary": "No hosts scanned.", "patterns": [], "priority_actions": []}

    total_open   = sum(h.get("open_count", 0) for h in hosts)
    critical_h   = [h for h in hosts if h.get("risk_level") in ("CRITICAL", "HIGH")]
    all_services = {}
    for h in hosts:
        for p in h.get("open_ports", []):
            svc = p.get("service", "unknown")
            all_services[svc] = all_services.get(svc, 0) + 1

    top_services = sorted(all_services.items(), key=lambda x: x[1], reverse=True)[:10]

    system = """You are a senior network security engineer writing an executive briefing.
Respond with valid JSON only.
Format: {"executive_summary": "...", "key_findings": ["..."],
"patterns": ["..."], "priority_actions": ["..."], "compliance_notes": ["..."]}"""

    user = f"""Network reconnaissance summary for executive report:

Hosts scanned: {len(hosts)}
Total open ports: {total_open}
High/Critical risk hosts: {len(critical_h)} ({', '.join(h['ip'] for h in critical_h[:5])})
Most common services: {', '.join(f"{s}({c})" for s,c in top_services)}
Average risk score: {sum(h.get('risk_score',0) for h in hosts)/len(hosts):.1f}

Write a concise executive summary (3 sentences), key findings (4 bullets),
network patterns, and top 5 priority remediation actions.
Focus on business risk, not just technical details."""

    raw = _call_claude(system, user, max_tokens=900)

    if raw.startswith("_"):
        return _rule_based_network_analysis(hosts)

    try:
        result = json.loads(raw)
        result["ai_available"] = True
        return result
    except json.JSONDecodeError:
        return _rule_based_network_analysis(hosts)


def generate_remediation_script(host_data: dict) -> str:
    """
    Generate a bash remediation script for detected issues.
    """
    open_ports  = host_data.get("open_ports", [])
    critical    = [p for p in open_ports if p.get("risk") in ("critical", "high")]

    if not critical:
        return "#!/bin/bash\n# No critical issues found — no remediation needed\necho 'Host looks clean.'\n"

    system = """You are a Linux security hardening expert.
Generate a bash script that remediates the security issues found.
Include comments explaining each step. Use systemctl, ufw, iptables as appropriate.
Start with #!/bin/bash and include safety checks. Keep it under 60 lines."""

    issues = "\n".join(
        f"- port {p['port']} ({p['service']}) risk={p['risk']}: {p['notes']}"
        for p in critical
    )

    user = f"""Generate a remediation bash script for:
Host: {host_data.get('ip')}
OS hint: {host_data.get('os_hint', 'Linux')}
Issues:
{issues}

Include: disabling dangerous services, firewall rules, config hardening."""

    raw = _call_claude(system, user, max_tokens=600)

    if raw.startswith("_"):
        return _rule_based_script(critical)

    return raw


# ── Rule-based fallback (no API key needed) ───────────────────────────────────

def _rule_based_analysis(host_data: dict) -> dict:
    open_ports = host_data.get("open_ports", [])
    risk_level = host_data.get("risk_level", "NONE")
    anomalies, recommendations, vectors = [], [], []

    for p in open_ports:
        risk = p.get("risk", "")
        svc  = p.get("service", "")
        port = p.get("port", 0)

        if risk == "critical":
            anomalies.append(f"Critical service exposed: {svc} on port {port}")
            vectors.append(f"Direct attack on {svc} (port {port})")

        if port == 23:
            anomalies.append("Telnet enabled — transmits credentials in cleartext")
            recommendations.append("Disable telnet, replace with SSH immediately")
        if port == 6379:
            anomalies.append("Redis exposed — likely unauthenticated")
            recommendations.append("Bind Redis to 127.0.0.1, enable requirepass")
        if port == 9200:
            anomalies.append("Elasticsearch exposed — data breach risk")
            recommendations.append("Add authentication, restrict to internal network")
        if port == 27017:
            anomalies.append("MongoDB exposed — check authentication")
            recommendations.append("Enable MongoDB auth, bind to localhost only")
        if port == 3389:
            recommendations.append("Restrict RDP to VPN only, enable NLA")
        if port == 445:
            anomalies.append("SMB exposed — EternalBlue/WannaCry risk")
            recommendations.append("Block SMB at perimeter, patch MS17-010")

    if not recommendations:
        recommendations.append("Review firewall rules and close unused ports")
        recommendations.append("Ensure all services are on latest patch level")

    return {
        "summary":         f"Host has {host_data.get('open_count',0)} open ports. Risk level: {risk_level}.",
        "threat_level":    risk_level,
        "anomalies":       anomalies[:5],
        "recommendations": recommendations[:5],
        "attack_vectors":  vectors[:3],
        "ai_available":    False,
    }


def _rule_based_network_analysis(hosts: list[dict]) -> dict:
    critical = [h for h in hosts if h.get("risk_level") in ("CRITICAL","HIGH")]
    total_open = sum(h.get("open_count", 0) for h in hosts)
    return {
        "executive_summary": (
            f"Network scan of {len(hosts)} hosts revealed {total_open} open ports. "
            f"{len(critical)} hosts present HIGH or CRITICAL risk. "
            "Immediate remediation recommended for flagged hosts."
        ),
        "key_findings": [
            f"{len(critical)} high/critical risk hosts detected",
            f"{total_open} total open ports across the network",
            "Rule-based analysis (set ANTHROPIC_API_KEY for AI analysis)",
        ],
        "patterns":          ["Multiple database ports exposed", "Legacy protocols detected"],
        "priority_actions":  ["Audit all critical-risk hosts immediately", "Close unused ports", "Enable firewall rules"],
        "compliance_notes":  ["Review against CIS Benchmarks", "Check PCI-DSS port requirements"],
        "ai_available":      False,
    }


def _rule_based_script(critical_ports: list) -> str:
    lines = ["#!/bin/bash", "# Auto-generated remediation script — kt-it26/netrecon-ai", "set -e", ""]
    for p in critical_ports:
        port = p.get("port")
        svc  = p.get("service", "")
        lines.append(f"# Remediate port {port} ({svc})")
        if port == 6379:
            lines += ["sed -i 's/^bind .*/bind 127.0.0.1/' /etc/redis/redis.conf",
                      "systemctl restart redis", ""]
        elif port == 23:
            lines += ["systemctl disable telnet", "systemctl stop telnet",
                      "ufw deny 23/tcp", ""]
        elif port == 9200:
            lines += ["# Add Elasticsearch auth — edit /etc/elasticsearch/elasticsearch.yml",
                      "# xpack.security.enabled: true", ""]
        else:
            lines += [f"ufw deny {port}/tcp  # block {svc}", ""]
    lines += ["echo 'Remediation script complete — verify each change manually'"]
    return "\n".join(lines)
