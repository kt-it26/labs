#!/usr/bin/env bash
# scripts/port-health.sh
# Quick port health check — no Python needed
# Usage: bash port-health.sh [host] [port1,port2,...]

HOST="${1:-localhost}"
PORTS="${2:-22,80,443,3306,5432,6379,8080}"
TIMEOUT=2

GREEN='\033[92m'; RED='\033[91m'; RESET='\033[0m'; BOLD='\033[1m'; DIM='\033[90m'

echo -e "\n${BOLD}  PORT HEALTH · kt-it26${RESET}"
echo -e "  ${DIM}host: $HOST${RESET}\n"
printf "  %-8s %-18s %-10s %s\n" "PORT" "SERVICE" "STATUS" "LATENCY"
printf "  %-8s %-18s %-10s %s\n" "────────" "──────────────────" "──────────" "──────────"

declare -A SERVICES=(
    [21]="FTP" [22]="SSH" [25]="SMTP" [53]="DNS"
    [80]="HTTP" [443]="HTTPS" [3306]="MySQL"
    [5432]="PostgreSQL" [6379]="Redis" [8080]="HTTP-alt"
    [27017]="MongoDB" [9200]="Elasticsearch" [9092]="Kafka"
)

IFS=',' read -ra PORT_LIST <<< "$PORTS"
OPEN=0; CLOSED=0

for PORT in "${PORT_LIST[@]}"; do
    SERVICE="${SERVICES[$PORT]:-unknown}"
    START=$(date +%s%3N)

    if timeout "$TIMEOUT" bash -c "echo >/dev/tcp/$HOST/$PORT" 2>/dev/null; then
        END=$(date +%s%3N)
        LAT=$(( END - START ))
        printf "  ${GREEN}●${RESET} %-6s %-18s ${GREEN}%-10s${RESET} %s\n" "$PORT" "$SERVICE" "open" "${LAT}ms"
        (( OPEN++ )) || true
    else
        printf "  ${RED}○${RESET} %-6s %-18s ${RED}%-10s${RESET} %s\n" "$PORT" "$SERVICE" "closed" "—"
        (( CLOSED++ )) || true
    fi
done

echo ""
echo -e "  ${GREEN}Open: $OPEN${RESET}   ${RED}Closed: $CLOSED${RESET}   Total: $(( OPEN + CLOSED ))"
echo ""
